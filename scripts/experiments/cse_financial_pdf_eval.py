#!/usr/bin/env python3
"""CSE financial PDF extraction spike — download ~100 filings and score parsers.

Polite rate-limiting against cse.lk / cdn.cse.lk. Not wired into the poller.
Outputs JSON + markdown under docs/experiments/.

Usage:
  python3 scripts/experiments/cse_financial_pdf_eval.py
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve()
# scripts/experiments/cse_financial_pdf_eval.py → repo root
REPO = Path(__file__).resolve().parents[2]
OUT_DIR = REPO / "docs" / "experiments"
PDF_DIR = Path("/tmp/cse-financial-pdfs")
TARGET_PDFS = 100
SLEEP_S = 0.35
UA = "Mozilla/5.0 (compatible; ChimeBot/0.1; financial-pdf-eval)"

# Heuristic metric detectors (not ground-truth — measures "can we find candidates")
METRIC_PATTERNS: dict[str, re.Pattern[str]] = {
    "revenue": re.compile(
        r"\b(revenue|turnover|total\s+income|group\s+revenue|net\s+sales)\b",
        re.I,
    ),
    "profit": re.compile(
        r"\b(profit\s+for\s+the\s+(period|year)|net\s+profit|profit\s+attributable|"
        r"profit\s+after\s+tax|loss\s+for\s+the\s+(period|year))\b",
        re.I,
    ),
    "eps": re.compile(
        r"\b(earnings?\s+per\s+share|basic\s+eps|diluted\s+eps|EPS)\b",
        re.I,
    ),
    "assets": re.compile(
        r"\b(total\s+assets|total\s+equity|shareholders[’']?\s+funds)\b",
        re.I,
    ),
}

# Number near a metric label (very rough — for "calculable candidate" scoring)
NUMBER_NEAR = re.compile(
    r"([A-Za-z][A-Za-z\s/%()]{2,40}?)\s*[:=\-]?\s*"
    r"(\(?-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\)?)",
)


@dataclass
class PdfEval:
    symbol: str
    kind: str  # annual | quarterly
    title: str
    url: str
    bytes: int | None = None
    pages_pypdf: int | None = None
    chars_pypdf: int = 0
    chars_pdfplumber: int = 0
    download_ok: bool = False
    text_ok: bool = False
    scanned_like: bool = False
    metrics_found: dict[str, bool] | None = None
    number_hits: int = 0
    error: str | None = None


def _request(
    url: str,
    *,
    data: bytes | None = None,
    content_type: str | None = None,
    timeout: int = 60,
) -> bytes:
    headers = {
        "User-Agent": UA,
        "Origin": "https://www.cse.lk",
        "Referer": "https://www.cse.lk/",
        "Accept": "*/*",
    }
    method = "GET"
    if data is not None:
        method = "POST"
        headers["Content-Type"] = content_type or "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def post_json(path: str, *, form: str | None = None, json_body: str | None = None) -> object:
    if json_body is not None:
        raw = _request(
            f"https://www.cse.lk/api/{path}",
            data=json_body.encode(),
            content_type="application/json",
        )
    else:
        raw = _request(
            f"https://www.cse.lk/api/{path}",
            data=(form or "").encode(),
            content_type="application/x-www-form-urlencoded",
        )
    return json.loads(raw)


def cdn_url(path: str) -> str | None:
    if not isinstance(path, str) or not path.strip():
        return None
    from urllib.parse import quote

    p = path.strip().lstrip("/")
    if not p.lower().endswith(".pdf"):
        return None
    # Legacy rows sometimes omit cmt/
    if not p.startswith("cmt/") and p.startswith("upload_report_file/"):
        p = f"cmt/{p}"
    # CSE paths sometimes include spaces / parentheses — encode path segments.
    enc = "/".join(quote(seg, safe="._-") for seg in p.split("/"))
    return f"https://cdn.cse.lk/{enc}"


def extract_pypdf(data: bytes, *, max_pages: int = 40) -> tuple[int, str]:
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(data))
    n = len(reader.pages)
    parts: list[str] = []
    for i, page in enumerate(reader.pages[:max_pages]):
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            continue
    return n, "\n".join(parts)


def extract_pdfplumber(data: bytes, *, max_pages: int = 25) -> str:
    import pdfplumber

    parts: list[str] = []
    with pdfplumber.open(BytesIO(data)) as pdf:
        for page in pdf.pages[:max_pages]:
            try:
                parts.append(page.extract_text() or "")
            except Exception:
                continue
    return "\n".join(parts)


def score_text(text: str) -> tuple[dict[str, bool], int, bool]:
    metrics = {name: bool(pat.search(text)) for name, pat in METRIC_PATTERNS.items()}
    # Count plausible financial numbers (comma-grouped or decimals)
    nums = re.findall(r"\(?-?(?:\d{1,3}(?:,\d{3})+|\d{4,})(?:\.\d+)?\)?", text)
    scanned_like = len(text.strip()) < 400
    return metrics, len(nums), scanned_like


def collect_targets(limit: int = TARGET_PDFS) -> list[dict]:
    board = post_json("tradeSummary", json_body="{}")
    assert isinstance(board, dict)
    rows = board.get("reqTradeSummery") or []
    symbols = []
    for row in rows:
        if isinstance(row, dict) and isinstance(row.get("symbol"), str):
            symbols.append(row["symbol"].strip().upper())
    symbols = sorted(set(symbols))

    out: list[dict] = []
    seen_urls: set[str] = set()
    for sym in symbols:
        if len(out) >= limit:
            break
        time.sleep(SLEEP_S)
        try:
            fin = post_json("financials", form=f"symbol={sym}")
        except Exception as exc:
            print(f"  financials fail {sym}: {exc}")
            continue
        if not isinstance(fin, dict):
            continue
        for kind, key in (
            ("quarterly", "infoQuarterlyData"),
            ("annual", "infoAnnualData"),
        ):
            items = fin.get(key) or []
            if not isinstance(items, list) or not items:
                continue
            # Prefer newest: API appears newest-first
            for item in items[:2]:
                if len(out) >= limit:
                    break
                if not isinstance(item, dict):
                    continue
                url = cdn_url(str(item.get("path") or ""))
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                out.append(
                    {
                        "symbol": sym,
                        "kind": kind,
                        "title": str(item.get("fileText") or kind),
                        "url": url,
                        "id": item.get("id"),
                    }
                )
        print(f"  collected {len(out)}/{limit} after {sym}")
    return out


def eval_one(meta: dict) -> PdfEval:
    row = PdfEval(
        symbol=meta["symbol"],
        kind=meta["kind"],
        title=meta["title"],
        url=meta["url"],
    )
    try:
        time.sleep(SLEEP_S)
        data = _request(meta["url"], timeout=90)
        row.bytes = len(data)
        row.download_ok = data[:5] == b"%PDF-" or data[:4] == b"%PDF"
        if not row.download_ok:
            # some CDNs still PDF without strict magic; accept application-ish size
            row.download_ok = len(data) > 1000
        if not row.download_ok:
            row.error = "not_pdf"
            return row

        PDF_DIR.mkdir(parents=True, exist_ok=True)
        safe = f"{meta['symbol']}_{meta['kind']}_{meta.get('id')}.pdf".replace("/", "_")
        (PDF_DIR / safe).write_bytes(data)

        pages, text_p = extract_pypdf(data)
        row.pages_pypdf = pages
        row.chars_pypdf = len(text_p)
        try:
            text_b = extract_pdfplumber(data)
            row.chars_pdfplumber = len(text_b)
        except Exception as exc:
            text_b = ""
            row.error = f"pdfplumber:{exc}"[:200]

        best = text_p if len(text_p) >= len(text_b) else text_b
        row.text_ok = len(best.strip()) >= 400
        metrics, number_hits, scanned = score_text(best)
        row.metrics_found = metrics
        row.number_hits = number_hits
        row.scanned_like = scanned or not row.text_ok
    except urllib.error.HTTPError as exc:
        row.error = f"http_{exc.code}"
    except Exception as exc:
        row.error = str(exc)[:240]
    return row


def summarize(rows: list[PdfEval]) -> dict:
    n = len(rows)
    dl = sum(1 for r in rows if r.download_ok)
    text = sum(1 for r in rows if r.text_ok)
    scanned = sum(1 for r in rows if r.scanned_like)
    metric_counts = Counter()
    for r in rows:
        if not r.metrics_found:
            continue
        for k, ok in r.metrics_found.items():
            if ok:
                metric_counts[k] += 1
    # "calculable-ish": text ok + at least revenue OR profit + eps-ish OR numbers
    calcish = 0
    for r in rows:
        if not r.text_ok or not r.metrics_found:
            continue
        m = r.metrics_found
        if (m.get("revenue") or m.get("profit")) and r.number_hits >= 20:
            calcish += 1
    strong = 0
    for r in rows:
        if not r.text_ok or not r.metrics_found:
            continue
        m = r.metrics_found
        if m.get("revenue") and m.get("profit") and m.get("eps") and r.number_hits >= 40:
            strong += 1

    def pct(x: int) -> float:
        return round(100.0 * x / n, 1) if n else 0.0

    return {
        "n": n,
        "download_ok": dl,
        "download_pct": pct(dl),
        "text_ok": text,
        "text_pct": pct(text),
        "scanned_like": scanned,
        "scanned_pct": pct(scanned),
        "metric_hit_counts": dict(metric_counts),
        "metric_hit_pct": {k: pct(v) for k, v in metric_counts.items()},
        "calcish_candidates": calcish,
        "calcish_pct": pct(calcish),
        "strong_eps_bundle": strong,
        "strong_pct": pct(strong),
        "kinds": dict(Counter(r.kind for r in rows)),
        "errors": dict(Counter(r.error for r in rows if r.error)),
    }


def write_report(rows: list[PdfEval], summary: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    json_path = OUT_DIR / f"cse_financial_pdf_eval_{stamp}.json"
    md_path = OUT_DIR / "CSE_FINANCIAL_PDF_EVAL.md"
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "target": TARGET_PDFS,
        "tools": ["pypdf", "pdfplumber"],
        "note": (
            "Heuristic label/number detection — not audited ground-truth accuracy. "
            "Measures extractability of CSE annual/quarterly PDFs for a future calc spike."
        ),
        "summary": summary,
        "rows": [asdict(r) for r in rows],
    }
    json_path.write_text(json.dumps(payload, indent=2))

    md = f"""# CSE financial PDF extraction spike

Generated: `{payload['generated_at']}`  
Sample: **{summary['n']}** PDFs from `POST /api/financials` (annual + quarterly), parsed with **pypdf** + **pdfplumber**.

## Headline

| Metric | Count | % |
|---|---:|---:|
| Downloaded OK | {summary['download_ok']} | {summary['download_pct']} |
| Extractable text (≥400 chars) | {summary['text_ok']} | {summary['text_pct']} |
| Scanned / empty-like | {summary['scanned_like']} | {summary['scanned_pct']} |
| Calc-ish candidates (rev/profit labels + ≥20 numbers) | {summary['calcish_candidates']} | {summary['calcish_pct']} |
| Strong bundle (rev+profit+EPS labels + ≥40 numbers) | {summary['strong_eps_bundle']} | {summary['strong_pct']} |

### Metric label hits (among all PDFs)

| Label family | Hit % |
|---|---:|
"""
    for k, v in sorted(summary.get("metric_hit_pct", {}).items()):
        md += f"| {k} | {v} |\n"

    md += f"""

## Interpretation for Chime

- This spike measures **whether text/tables are machine-readable enough to attempt calcs**, not whether computed EPS/PE would be correct.
- Open-source US tools that look strong usually lean on **XBRL** (`edgartools`). CSE public archives are **PDFs**, so expect FinTable-style parsers to need heavy per-issuer tweaking.
- Recommended next tweak if we continue: only run calc attempts on the **strong bundle** subset; keep Telegram on narrative briefs; never push unverified ratios.

## Errors

```json
{json.dumps(summary.get('errors', {}), indent=2)}
```

## Kinds

```json
{json.dumps(summary.get('kinds', {}), indent=2)}
```

Raw machine output: `{json_path.name}`
"""
    md_path.write_text(md)
    print("wrote", json_path)
    print("wrote", md_path)


def main() -> None:
    print("collecting PDF targets…")
    targets = collect_targets(TARGET_PDFS)
    print(f"targets={len(targets)}")
    rows: list[PdfEval] = []
    for i, meta in enumerate(targets, 1):
        print(f"[{i}/{len(targets)}] {meta['symbol']} {meta['kind']}")
        rows.append(eval_one(meta))
    summary = summarize(rows)
    write_report(rows, summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
