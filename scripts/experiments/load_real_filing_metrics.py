#!/usr/bin/env python3
"""One-off backfill: real cse.lk financial statement PDFs → filing_metrics + YoY.

``getAnnouncementByCompany`` mostly surfaces errata/amendment rows without a
resolvable CDN PDF, so this uses the same undocumented ``POST /financials``
endpoint the EPS real-world stress harness
(``scripts/experiments/cse_eps_realworld_stress.py``) validated at 100%
extract coverage across the board — it returns ``infoQuarterlyData`` /
``infoAnnualData`` with a direct CDN ``path`` per filing.

For each symbol: fetch financials, build a synthetic ``disclosures`` row per
statement PDF (FK required by ``filing_metrics``), download the PDF with
browser-like headers (cdn.cse.lk 403s on the bare httpx default UA), then run
the *production* extract + YoY compare pipeline
(``koel.metrics.worker.process_disclosure_metrics``) against the bytes —
same code path the poller uses. Rules are not evaluated (no Telegram sends).

Usage:
  python3 scripts/experiments/load_real_filing_metrics.py
  python3 scripts/experiments/load_real_filing_metrics.py --symbols JKH.N0000,COMB.N0000
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

import httpx

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from koel.adapters.cse import allowed_cdn_pdf_url  # noqa: E402
from koel.domain import Disclosure  # noqa: E402
from koel.metrics import MetricsSettings  # noqa: E402
from koel.metrics.worker import process_disclosure_metrics  # noqa: E402
from koel.storage import Storage  # noqa: E402

DEFAULT_SYMBOLS = [
    "JKH.N0000",
    "COMB.N0000",
    "HNB.N0000",
    "SAMP.N0000",
    "LOLC.N0000",
    "DIAL.N0000",
    "HAYL.N0000",
    "CTC.N0000",
    "SPEN.N0000",
    "CARS.N0000",
]

QUARTERLY_PER_SYMBOL = 6
# Annual reports are large, image-heavy, and often carry a USD investor-summary
# page the extractor can mistake for the LKR statement (extract_ok=False) —
# quarterlies extract reliably, so skip annuals in this backfill.
ANNUAL_PER_SYMBOL = 0
SLEEP_BETWEEN_HTTP_S = 0.4
SLEEP_BETWEEN_SYMBOLS_S = 0.6
PDF_MAX_BYTES = 32_000_000  # annual reports run large (image-heavy); quarterlies are small

UA = "Mozilla/5.0 (compatible; KoelBot/0.1; filing-metrics-backfill)"
BROWSER_HEADERS = {
    "User-Agent": UA,
    "Origin": "https://www.cse.lk",
    "Referer": "https://www.cse.lk/",
    "Accept": "*/*",
}


def cdn_url(path: str | None) -> str | None:
    """``upload_report_file/...`` (or ``cmt/upload_report_file/...``) → CDN URL."""
    if not isinstance(path, str) or not path.strip():
        return None
    p = path.strip().lstrip("/")
    if not p.lower().endswith(".pdf"):
        return None
    if not p.startswith("cmt/") and p.startswith("upload_report_file/"):
        p = f"cmt/{p}"
    enc = "/".join(quote(seg, safe="._-") for seg in p.split("/"))
    return allowed_cdn_pdf_url(f"https://cdn.cse.lk/{enc}")


async def fetch_financials(client: httpx.AsyncClient, symbol: str) -> dict:
    resp = await client.post(
        "https://www.cse.lk/api/financials",
        data={"symbol": symbol},
        headers={**BROWSER_HEADERS, "Content-Type": "application/x-www-form-urlencoded"},
        timeout=30.0,
    )
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, dict) else {}


def pick_targets(financials: dict) -> list[dict]:
    out: list[dict] = []
    for kind, key, cap in (
        ("quarterly", "infoQuarterlyData", QUARTERLY_PER_SYMBOL),
        ("annual", "infoAnnualData", ANNUAL_PER_SYMBOL),
    ):
        items = financials.get(key) or []
        if not isinstance(items, list):
            continue
        rows = [i for i in items if isinstance(i, dict) and i.get("path")]
        rows.sort(key=lambda i: i.get("manualDate") or 0, reverse=True)
        newest_n = rows[:cap]
        # Process oldest-first within each kind: resolve_prior only sees
        # candidates already upserted, so a YoY prior must land before the
        # current filing that needs it.
        newest_n.reverse()
        for item in newest_n:
            out.append({**item, "_kind": kind})
    return out


async def process_one(
    *,
    storage: Storage,
    client: httpx.AsyncClient,
    symbol: str,
    item: dict,
    settings: MetricsSettings,
) -> str:
    pdf_url = cdn_url(item.get("path"))
    if not pdf_url:
        return "no_pdf_url"

    manual_date_ms = item.get("manualDate")
    if isinstance(manual_date_ms, (int, float)) and manual_date_ms > 0:
        published_at = datetime.fromtimestamp(manual_date_ms / 1000, tz=UTC)
    else:
        published_at = datetime.now(UTC)

    title = str(item.get("fileText") or f"{item['_kind']} financial statement")
    disc = Disclosure(
        external_id=f"fin-{item.get('id')}",
        symbol=symbol,
        company_name=None,
        title=title,
        category="Financial Statements",
        url=pdf_url,
        published_at=published_at,
        seen_at=datetime.now(UTC),
        pdf_url=pdf_url,
    )
    saved = await storage.upsert_disclosure(disc)

    await asyncio.sleep(SLEEP_BETWEEN_HTTP_S)
    try:
        resp = await client.get(pdf_url, headers=BROWSER_HEADERS, timeout=60.0)
        resp.raise_for_status()
        data = resp.content
    except Exception as exc:  # noqa: BLE001
        print(f"    pdf download failed: {exc!r}")
        return "download_failed"
    if not data or len(data) > PDF_MAX_BYTES:
        return "bad_pdf_size"

    result = await process_disclosure_metrics(
        storage=storage,
        disclosure=saved,
        rules=None,
        settings=settings,
        pdf_bytes=data,
    )
    if result is None:
        return "skipped"
    if result.extract_ok:
        return f"ok compared={result.compared}"
    return "extract_failed"


async def run(symbols: list[str], database_url: str) -> None:
    settings = MetricsSettings(
        financial_metrics_enabled=True,
        filing_compare_enabled=True,
    )
    storage = Storage(database_url, max_size=2)
    await storage.open()

    totals = {"disclosures_upserted": 0, "extract_ok": 0, "extract_failed": 0, "compared": 0}

    async with httpx.AsyncClient() as client:
        try:
            for symbol in symbols:
                print(f"=== {symbol} ===")
                try:
                    financials = await fetch_financials(client, symbol)
                except Exception as exc:  # noqa: BLE001
                    print(f"  /financials fetch failed: {exc!r}")
                    continue
                targets = pick_targets(financials)
                if not targets:
                    print("  no quarterly/annual statement PDFs listed")
                    continue

                for item in targets:
                    outcome = await process_one(
                        storage=storage,
                        client=client,
                        symbol=symbol,
                        item=item,
                        settings=settings,
                    )
                    totals["disclosures_upserted"] += 1
                    if outcome.startswith("ok"):
                        totals["extract_ok"] += 1
                        if "compared=True" in outcome:
                            totals["compared"] += 1
                    elif outcome == "extract_failed":
                        totals["extract_failed"] += 1
                    label = item.get("fileText", "")[:55]
                    print(f"  {item.get('id')} {item['_kind']:9s} {label!r} -> {outcome}")
                    await asyncio.sleep(SLEEP_BETWEEN_HTTP_S)

                await asyncio.sleep(SLEEP_BETWEEN_SYMBOLS_S)
        finally:
            await storage.close()

    print("\nTOTALS", totals)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--symbols",
        type=str,
        default=None,
        help="Comma-separated symbol list (default: curated blue-chip set)",
    )
    args = ap.parse_args()

    symbols = (
        [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
        if args.symbols
        else DEFAULT_SYMBOLS
    )

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL not set", file=sys.stderr)
        raise SystemExit(1)

    if sys.platform == "win32":
        # psycopg async requires a selector-based loop; Windows defaults to Proactor.
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(run(symbols, database_url))


if __name__ == "__main__":
    main()
