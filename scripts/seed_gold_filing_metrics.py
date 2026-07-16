#!/usr/bin/env python3
"""Bridge research gold + prior PDF-eval CDN URLs into live Postgres metrics.

Seeds ``stocks`` / ``disclosures`` (with ``pdf_url``) from:
  - docs/experiments/cse_financial_gold_labels.json
  - docs/experiments/cse_financial_pdf_eval_*.json (CDN URLs)

Then runs ``process_disclosure_metrics`` with metrics flags on so the dash
symbol page can show filing metrics / YoY. Research bridge — not a product
scraper of competitors.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from chime.domain import Disclosure  # noqa: E402
from chime.metrics import MetricsSettings  # noqa: E402
from chime.metrics.worker import process_disclosure_metrics  # noqa: E402
from chime.storage import Storage  # noqa: E402

EXP = ROOT / "docs" / "experiments"


def _load_gold() -> list[dict]:
    path = EXP / "cse_financial_gold_labels.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _load_eval_rows() -> list[dict]:
    priors = sorted(EXP.glob("cse_financial_pdf_eval_*.json"))
    if not priors:
        raise SystemExit("No cse_financial_pdf_eval_*.json under docs/experiments")
    data = json.loads(priors[-1].read_text(encoding="utf-8"))
    rows = data.get("rows") or []
    if not isinstance(rows, list):
        raise SystemExit(f"Unexpected eval shape in {priors[-1].name}")
    print(f"Using eval: {priors[-1].name} ({len(rows)} rows)")
    return rows


def _match_eval(eval_rows: list[dict], symbol: str, kind: str) -> dict | None:
    exact = [
        r
        for r in eval_rows
        if r.get("symbol") == symbol
        and r.get("kind") == kind
        and r.get("download_ok")
        and isinstance(r.get("url"), str)
        and r["url"].startswith("https://cdn.cse.lk/")
    ]
    if exact:
        return exact[0]
    # Fall back to any downloadable PDF for the symbol.
    any_ok = [
        r
        for r in eval_rows
        if r.get("symbol") == symbol
        and r.get("download_ok")
        and isinstance(r.get("url"), str)
        and r["url"].startswith("https://cdn.cse.lk/")
    ]
    return any_ok[0] if any_ok else None


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max gold rows to seed (0 = all matched)",
    )
    parser.add_argument(
        "--telegram-id",
        type=int,
        default=123456789,
        help="Demo user to attach watchlist items for",
    )
    args = parser.parse_args()

    os.environ.setdefault("FINANCIAL_METRICS_ENABLED", "1")
    os.environ.setdefault("FILING_COMPARE_ENABLED", "1")
    os.environ.setdefault("METRICS_SHADOW_MODE", "1")
    os.environ.setdefault("EPS_CALC_ALERTS_ENABLED", "0")
    os.environ.setdefault("YOY_COMPARE_ALERTS_ENABLED", "0")

    database_url = os.environ.get(
        "DATABASE_URL", "postgresql://chime:chime@localhost:5432/chime"
    )
    gold = _load_gold()
    eval_rows = _load_eval_rows()

    storage = Storage(database_url)
    await storage.open()
    cfg = MetricsSettings.from_env()
    print(
        "metrics flags:",
        f"enabled={cfg.financial_metrics_enabled}",
        f"compare={cfg.filing_compare_enabled}",
    )

    user_id = await storage.ensure_user(args.telegram_id)

    seeded = 0
    extract_ok = 0
    extract_fail = 0
    skipped_no_pdf = 0
    comparisons: list[dict] = []

    now = datetime.now(UTC)
    for g in gold:
        symbol = str(g["symbol"])
        kind = str(g.get("kind") or "unknown")
        matched = _match_eval(eval_rows, symbol, kind)
        if matched is None:
            print(f"SKIP {symbol} {kind}: no CDN URL in eval JSON")
            skipped_no_pdf += 1
            continue
        if args.limit and seeded >= args.limit:
            break

        title = str(
            matched.get("title")
            or (
                "Interim Financial Statements"
                if kind == "quarterly"
                else "Annual Report Financial Statements"
            )
        )
        pdf_url = str(matched["url"])
        digest = hashlib.sha1(pdf_url.encode("utf-8")).hexdigest()[:12]
        external_id = f"gold-{symbol}-{kind}-{digest}"

        await storage.upsert_stock(symbol, None)
        await storage.add_watch(user_id, symbol)

        disc = Disclosure(
            external_id=external_id,
            symbol=symbol,
            title=title,
            category="Financial",
            url=f"https://www.cse.lk/pages/company-profile/company-profile.component.html?symbol={symbol}",
            company_name=None,
            published_at=now,
            seen_at=now,
            pdf_url=pdf_url,
        )
        stored = await storage.upsert_disclosure(disc)
        if stored.id is not None and not stored.pdf_url:
            await storage.set_disclosure_pdf_url(stored.id, pdf_url)
            stored = await storage.get_disclosure_by_id(stored.id) or stored

        result = await process_disclosure_metrics(
            storage=storage,
            disclosure=stored,
            rules=[],
            settings=cfg,
        )
        seeded += 1
        ok = bool(result and result.extract_ok)
        if ok:
            extract_ok += 1
        else:
            extract_fail += 1

        # Pull stored metrics for gold compare
        metrics_list = await storage.list_filing_metrics_for_symbol(symbol)
        latest = next(
            (m for m in metrics_list if int(m.get("disclosure_id") or -1) == stored.id),
            metrics_list[0] if metrics_list else None,
        )
        gold_eps = g.get("eps_basic")
        got_eps = latest.get("eps_basic") if latest else None
        eps_match = (
            gold_eps is not None
            and got_eps is not None
            and abs(float(got_eps) - float(gold_eps)) < 0.02
        )
        comparisons.append(
            {
                "symbol": symbol,
                "kind": kind,
                "extract_ok": ok,
                "gold_eps": gold_eps,
                "got_eps": got_eps,
                "eps_match": eps_match,
                "disclosure_id": stored.id,
                "pdf_url": pdf_url,
            }
        )
        print(
            f"{'OK' if ok else 'FAIL'} {symbol} {kind} "
            f"gold_eps={gold_eps} got_eps={got_eps} match={eps_match}"
        )

    await storage.close()

    matched_n = sum(1 for c in comparisons if c["gold_eps"] is not None)
    hits = sum(1 for c in comparisons if c["eps_match"])
    print("---")
    print(
        json.dumps(
            {
                "seeded": seeded,
                "skipped_no_pdf": skipped_no_pdf,
                "extract_ok": extract_ok,
                "extract_fail": extract_fail,
                "gold_eps_rows": matched_n,
                "eps_matches": hits,
                "eps_match_pct": round(100.0 * hits / matched_n, 1) if matched_n else 0.0,
            },
            indent=2,
        )
    )
    return 0 if extract_ok > 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
