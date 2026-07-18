#!/usr/bin/env python3
"""Research-only spike: pull LOLC StockLens + dividend CSV (+ CDS INFOLINE index).

No Postgres writes. No prod flags. Polite GETs only.

Usage:
  python3 scripts/experiments/lolc_public_feeds_spike.py
  python3 scripts/experiments/lolc_public_feeds_spike.py --skip-cds
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import statistics
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT_DIR = REPO / "docs" / "experiments"
SAMPLE_DIR = REPO / "docs" / "sample_responses"

STOCKLENS_URL = "https://www.lolcsecurities.lk/api/stock-screener/"
DIVIDENDS_URL = "https://www.lolcsecurities.lk/dividend-calendar/dividends_db.csv"
CDS_MONTHLY_URL = (
    "https://www.cds.lk/services/depository-operations/"
    "publications-downloads/cds-monthly-reports/"
)

UA = "ChimeResearch/1.0 (+https://github.com/Cookie-Cat21/Chime; educational; polite)"


def _get(url: str, timeout: float = 30.0) -> tuple[int, bytes, dict[str, str]]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "*/*",
            "Referer": "https://www.lolcsecurities.lk/",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            headers = {k.lower(): v for k, v in resp.headers.items()}
            return resp.status, resp.read(), headers
    except urllib.error.HTTPError as e:
        return e.code, e.read() if e.fp else b"", {}


def parse_num(value: object) -> float | None:
    if value is None:
        return None
    s = str(value).strip().replace(",", "").replace("%", "")
    if s in ("", "-", "N/A", "null", "None", "—"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_date(value: str | None) -> date | None:
    s = (value or "").strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def coverage(rows: list[dict], key: str) -> dict[str, object]:
    vals = [parse_num(r.get(key)) for r in rows]
    ok = [v for v in vals if v is not None]
    out: dict[str, object] = {
        "field": key,
        "non_null": len(ok),
        "n": len(rows),
        "pct": round(100.0 * len(ok) / len(rows), 1) if rows else 0.0,
    }
    if ok:
        out["median"] = round(statistics.median(ok), 4)
        out["min"] = round(min(ok), 4)
        out["max"] = round(max(ok), 4)
    return out


def analyze_stocklens(payload: dict) -> dict:
    rows = payload.get("data") or []
    if not isinstance(rows, list):
        return {"error": "data not a list"}
    keys = list(rows[0].keys()) if rows else []
    tickers = [
        str(r.get("Company Tiker") or r.get("Company Ticker") or "").strip()
        for r in rows
    ]
    tickers = [t for t in tickers if t]
    sectors = Counter(str(r.get("Sector") or "") for r in rows)

    numeric_fields = [
        "Market Price (LKR)",
        "Market Capitalization (LKR Mn)",
        "Foreign Holding%",
        "4QT Earnings (LKR Mn)",
        "PE (x)",
        "Sector PE (x)",
        "PBV (x)",
        "Sector PBV (x)",
        "DY (%)",
        "DPS (LKR)",
        "EPS 4QT (LKR)",
        "NAV (LKR)",
        "ROE (%)",
    ]
    cov = [coverage(rows, f) for f in numeric_fields]

    # Sector-relative PE (research signal for F-xxx)
    cheap: list[tuple[float, str, float, float]] = []
    for r in rows:
        pe = parse_num(r.get("PE (x)"))
        spe = parse_num(r.get("Sector PE (x)"))
        sym = str(r.get("Company Tiker") or "").strip()
        if pe is None or spe is None or spe <= 0 or pe <= 0 or pe > 200:
            continue
        cheap.append((pe / spe, sym, pe, spe))
    cheap.sort()

    fh = [parse_num(r.get("Foreign Holding%")) for r in rows]
    fh_ok = sorted(v for v in fh if v is not None)

    return {
        "last_modified": payload.get("last_modified"),
        "n_rows": len(rows),
        "n_tickers": len(set(tickers)),
        "keys": keys,
        "sectors": len(sectors),
        "sector_top": sectors.most_common(8),
        "coverage": cov,
        "foreign_holding": {
            "n": len(fh_ok),
            "median": round(statistics.median(fh_ok), 3) if fh_ok else None,
            "p90": round(fh_ok[int(0.9 * (len(fh_ok) - 1))], 3) if fh_ok else None,
            "max": round(fh_ok[-1], 3) if fh_ok else None,
            "high_fh_sample": [
                {
                    "symbol": str(r.get("Company Tiker")),
                    "fh_pct": parse_num(r.get("Foreign Holding%")),
                    "name": r.get("Company Name"),
                }
                for r in sorted(
                    rows,
                    key=lambda x: parse_num(x.get("Foreign Holding%")) or -1,
                    reverse=True,
                )[:8]
            ],
        },
        "pe_vs_sector_cheapest": [
            {"symbol": s, "pe_over_sector": round(ratio, 3), "pe": pe, "sector_pe": spe}
            for ratio, s, pe, spe in cheap[:8]
        ],
        "pe_vs_sector_richest": [
            {"symbol": s, "pe_over_sector": round(ratio, 3), "pe": pe, "sector_pe": spe}
            for ratio, s, pe, spe in cheap[-5:]
        ],
        "sample_normalized_row": _normalize_stocklens_row(rows[0]) if rows else None,
        "suffix_mix": dict(Counter(t.split(".")[-1] if "." in t else "?" for t in tickers)),
    }


def _normalize_stocklens_row(r: dict) -> dict:
    return {
        "symbol": str(r.get("Company Tiker") or "").strip(),
        "name": r.get("Company Name"),
        "sector": r.get("Sector"),
        "price": parse_num(r.get("Market Price (LKR)")),
        "mcap_mn": parse_num(r.get("Market Capitalization (LKR Mn)")),
        "foreign_holding_pct": parse_num(r.get("Foreign Holding%")),
        "pe": parse_num(r.get("PE (x)")),
        "sector_pe": parse_num(r.get("Sector PE (x)")),
        "pbv": parse_num(r.get("PBV (x)")),
        "sector_pbv": parse_num(r.get("Sector PBV (x)")),
        "dy_pct": parse_num(r.get("DY (%)")),
        "dps": parse_num(r.get("DPS (LKR)")),
        "eps_4qt": parse_num(r.get("EPS 4QT (LKR)")),
        "nav": parse_num(r.get("NAV (LKR)")),
        "roe_pct": parse_num(r.get("ROE (%)")),
    }


def analyze_dividends(csv_text: str, as_of: date) -> dict:
    reader = csv.DictReader(io.StringIO(csv_text))
    rows = list(reader)
    fields = reader.fieldnames or []
    codes = Counter(str(r.get("CODE") or "").strip() for r in rows)

    parsed = []
    for r in rows:
        xd = parse_date(r.get("D_XD"))
        if xd is None:
            continue
        parsed.append(
            {
                "symbol": str(r.get("CODE") or "").strip(),
                "d_ann": str(r.get("D_ANN") or ""),
                "d_xd": xd.isoformat(),
                "d_pay": str(r.get("D_PAY") or ""),
                "dps": parse_num(r.get("DPS")),
                "interim": (r.get("INTERIM") or "").strip(),
                "fy": (r.get("FY") or "").strip(),
            }
        )

    xds = [date.fromisoformat(p["d_xd"]) for p in parsed]
    upcoming = sorted(
        [p for p in parsed if date.fromisoformat(p["d_xd"]) >= as_of],
        key=lambda p: p["d_xd"],
    )
    # XD-soon alert simulation: fire if XD within N days
    horizon_hits = {}
    for n in (3, 7, 14, 30):
        end = as_of.toordinal() + n
        horizon_hits[str(n)] = sum(
            1 for p in upcoming if date.fromisoformat(p["d_xd"]).toordinal() <= end
        )

    return {
        "n_rows": len(rows),
        "n_parsed_xd": len(parsed),
        "fields": [f for f in fields if f],
        "unique_symbols": len([c for c in codes if c]),
        "xd_min": min(xds).isoformat() if xds else None,
        "xd_max": max(xds).isoformat() if xds else None,
        "upcoming_count": len(upcoming),
        "upcoming_next_15": upcoming[:15],
        "xd_soon_horizon_counts": horizon_hits,
        "top_symbols_by_history": codes.most_common(8),
        "sample_row": parsed[0] if parsed else None,
    }


def analyze_cds_index(html: str) -> dict:
    pdfs = re.findall(
        r'href="(https?://[^"]*CDS-INFOLINE[^"]+\.pdf)"',
        html,
        flags=re.I,
    )
    # also relative
    rel = re.findall(r'href="([^"]*CDS-INFOLINE[^"]+\.pdf)"', html, flags=re.I)
    urls = []
    for u in pdfs + rel:
        if u.startswith("http"):
            urls.append(u)
        else:
            urls.append("https://www.cds.lk" + (u if u.startswith("/") else "/" + u))
    # dedupe preserve order
    seen: set[str] = set()
    uniq = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            uniq.append(u)
    return {
        "n_pdf_links": len(uniq),
        "latest_5": uniq[:5],
    }


def truncate_stocklens_sample(payload: dict, n: int = 3) -> dict:
    rows = payload.get("data") or []
    return {
        "last_modified": payload.get("last_modified"),
        "data": rows[:n],
        "_truncated": True,
        "_original_row_count": len(rows),
        "_note": "Research sample only — not for redistribution as a full board dump.",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--skip-cds", action="store_true")
    ap.add_argument("--as-of", default=None, help="YYYY-MM-DD for XD horizon (default: today UTC)")
    args = ap.parse_args()

    as_of = (
        datetime.strptime(args.as_of, "%Y-%m-%d").date()
        if args.as_of
        else datetime.now(UTC).date()
    )
    started = datetime.now(UTC).isoformat()
    report: dict = {
        "started_at": started,
        "as_of": as_of.isoformat(),
        "purpose": "research-only spike — no prod ingest",
        "nfa": "Not financial advice. Metrics are descriptive only.",
        "sources": {},
        "analyses": {},
        "errors": [],
    }

    # --- StockLens ---
    print(f"GET {STOCKLENS_URL}")
    status, body, headers = _get(STOCKLENS_URL)
    report["sources"]["stocklens"] = {
        "url": STOCKLENS_URL,
        "http_status": status,
        "bytes": len(body),
        "content_type": headers.get("content-type"),
        "sha256": hashlib.sha256(body).hexdigest()[:16],
    }
    if status != 200:
        report["errors"].append(f"stocklens HTTP {status}")
    else:
        try:
            payload = json.loads(body.decode("utf-8"))
            report["analyses"]["stocklens"] = analyze_stocklens(payload)
            SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
            sample_path = SAMPLE_DIR / "lolc_stocklens_truncated.json"
            sample_path.write_text(
                json.dumps(truncate_stocklens_sample(payload), indent=2) + "\n",
                encoding="utf-8",
            )
            print(f"  wrote {sample_path.relative_to(REPO)}")
        except json.JSONDecodeError as e:
            report["errors"].append(f"stocklens JSON: {e}")

    time.sleep(0.5)

    # --- Dividends ---
    print(f"GET {DIVIDENDS_URL}")
    status, body, headers = _get(DIVIDENDS_URL)
    report["sources"]["dividends"] = {
        "url": DIVIDENDS_URL,
        "http_status": status,
        "bytes": len(body),
        "content_type": headers.get("content-type"),
        "sha256": hashlib.sha256(body).hexdigest()[:16],
    }
    if status != 200:
        report["errors"].append(f"dividends HTTP {status}")
    else:
        text = body.decode("utf-8", errors="replace")
        report["analyses"]["dividends"] = analyze_dividends(text, as_of)
        # truncated CSV sample (header + 5 rows)
        lines = text.splitlines()
        sample_csv = "\n".join(lines[:6]) + ("\n" if lines else "")
        csv_path = SAMPLE_DIR / "lolc_dividends_truncated.csv"
        csv_path.write_text(sample_csv, encoding="utf-8")
        print(f"  wrote {csv_path.relative_to(REPO)}")

    if not args.skip_cds:
        time.sleep(0.5)
        print(f"GET {CDS_MONTHLY_URL}")
        status, body, headers = _get(CDS_MONTHLY_URL, timeout=40.0)
        report["sources"]["cds_infoline_index"] = {
            "url": CDS_MONTHLY_URL,
            "http_status": status,
            "bytes": len(body),
            "content_type": headers.get("content-type"),
        }
        if status == 200:
            report["analyses"]["cds_infoline_index"] = analyze_cds_index(
                body.decode("utf-8", errors="replace")
            )
        else:
            report["errors"].append(f"cds index HTTP {status}")

    # Product-shaped takeaways (still research)
    sl = report["analyses"].get("stocklens") or {}
    div = report["analyses"].get("dividends") or {}
    report["takeaways"] = {
        "fundamentals_board_usable": bool(sl.get("n_rows", 0) >= 200),
        "foreign_holding_fills_f086_gap": bool(
            (sl.get("foreign_holding") or {}).get("n", 0) >= 200
        ),
        "xd_soon_alerts_near_term": (div.get("xd_soon_horizon_counts") or {}).get("14"),
        "would_need_for_prod": [
            "ToS / redistribution decision for LOLC",
            "Postgres tables + flag-default-0 adapters",
            "Attribution + as-of on dash",
            "CSE prices remain truth (ignore LOLC price for quotes)",
        ],
    }

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_json = OUT_DIR / f"lolc_public_feeds_spike_{stamp}.json"
    out_md = OUT_DIR / "LOLC_PUBLIC_FEEDS_SPIKE.md"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    md = _render_md(report, out_json.name)
    out_md.write_text(md, encoding="utf-8")
    print(f"wrote {out_json.relative_to(REPO)}")
    print(f"wrote {out_md.relative_to(REPO)}")
    if report["errors"]:
        print("errors:", report["errors"])
        return 1
    return 0


def _render_md(report: dict, json_name: str) -> str:
    sl = report.get("analyses", {}).get("stocklens") or {}
    div = report.get("analyses", {}).get("dividends") or {}
    cds = report.get("analyses", {}).get("cds_infoline_index") or {}
    fh = sl.get("foreign_holding") or {}
    lines = [
        "# LOLC / CDS public feeds spike (research-only)",
        "",
        f"**Ran:** `{report.get('started_at')}` · **as-of:** `{report.get('as_of')}`  ",
        f"**Machine report:** [`{json_name}`](./{json_name})  ",
        f"**Script:** `scripts/experiments/lolc_public_feeds_spike.py`",
        "",
        "> Not financial advice. No prod ingest. Truncated samples only — do not republish full boards.",
        "",
        "## What we pulled",
        "",
        "| Source | HTTP | Bytes | Notes |",
        "|---|---|---|---|",
    ]
    for name, meta in (report.get("sources") or {}).items():
        lines.append(
            f"| {name} | {meta.get('http_status')} | {meta.get('bytes')} | "
            f"`{meta.get('url')}` |"
        )

    lines += [
        "",
        "## StockLens",
        "",
        f"- Rows: **{sl.get('n_rows')}** · unique tickers: **{sl.get('n_tickers')}** · sectors: **{sl.get('sectors')}**",
        f"- `last_modified`: `{sl.get('last_modified')}`",
        f"- Suffix mix: `{sl.get('suffix_mix')}`",
        f"- Foreign holding coverage: **{fh.get('n')}** · median **{fh.get('median')}%** · p90 **{fh.get('p90')}%**",
        "",
        "### High foreign holding (sample)",
        "",
        "```json",
        json.dumps(fh.get("high_fh_sample"), indent=2),
        "```",
        "",
        "### Normalized row shape (adapter sketch)",
        "",
        "```json",
        json.dumps(sl.get("sample_normalized_row"), indent=2),
        "```",
        "",
        "## Dividends",
        "",
        f"- Rows: **{div.get('n_rows')}** · parsed XD: **{div.get('n_parsed_xd')}** · symbols: **{div.get('unique_symbols')}**",
        f"- XD range: `{div.get('xd_min')}` → `{div.get('xd_max')}`",
        f"- Upcoming from as-of: **{div.get('upcoming_count')}**",
        f"- XD-soon horizon counts (days → events): `{div.get('xd_soon_horizon_counts')}`",
        "",
        "### Next XD events",
        "",
        "```json",
        json.dumps(div.get("upcoming_next_15"), indent=2),
        "```",
        "",
        "## CDS INFOLINE index",
        "",
        f"- PDF links found: **{cds.get('n_pdf_links')}**",
        f"- Latest: `{cds.get('latest_5')}`",
        "",
        "## Takeaways",
        "",
        "```json",
        json.dumps(report.get("takeaways"), indent=2),
        "```",
        "",
        "## Errors",
        "",
        f"`{report.get('errors')}`",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
