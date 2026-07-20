#!/usr/bin/env python3
"""Real-world EPS extract stress test across the full CSE board.

Downloads financial PDFs for symbols not yet cached, runs the hardened
extractor, builds dual-agree gold, and scores calc-alert feasibility.

Usage:
  # Download next N *companies* (newest quarterly + annual each), then eval:
  python3 scripts/experiments/cse_eps_realworld_stress.py --companies 100

  # Eval only (use whatever PDFs are already cached):
  python3 scripts/experiments/cse_eps_realworld_stress.py --eval-only

  # Keep going until board exhausted:
  python3 scripts/experiments/cse_eps_realworld_stress.py --companies 9999
"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from importlib.machinery import SourceFileLoader
from pathlib import Path
from typing import Any
from urllib.parse import quote

REPO = Path(__file__).resolve().parents[2]
OUT_DIR = REPO / "docs" / "experiments"
PDF_DIR = Path("/tmp/cse-financial-pdfs")
SLEEP_S = 0.35
UA = "Mozilla/5.0 (compatible; KoelBot/0.1; eps-realworld-stress)"

ACC = SourceFileLoader(
    "cse_acc",
    str(REPO / "scripts" / "experiments" / "cse_financial_accuracy_eval.py"),
).load_module()
FEAS = SourceFileLoader(
    "cse_feas",
    str(REPO / "scripts" / "experiments" / "cse_eps_calc_alert_feasibility.py"),
).load_module()


@dataclass
class DlRow:
    symbol: str
    kind: str
    title: str
    url: str
    id: Any = None
    bytes: int | None = None
    pages: int | None = None
    chars: int = 0
    download_ok: bool = False
    text_ok: bool = False
    scanned_like: bool = False
    metrics_found: dict[str, bool] = field(default_factory=dict)
    number_hits: int = 0
    error: str | None = None
    pdf_path: str | None = None


def _request(
    url: str,
    *,
    data: bytes | None = None,
    content_type: str | None = None,
    timeout: int = 90,
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
    p = path.strip().lstrip("/")
    if not p.lower().endswith(".pdf"):
        return None
    if not p.startswith("cmt/") and p.startswith("upload_report_file/"):
        p = f"cmt/{p}"
    enc = "/".join(quote(seg, safe="._-") for seg in p.split("/"))
    return f"https://cdn.cse.lk/{enc}"


def live_symbols() -> list[str]:
    board = post_json("tradeSummary", json_body="{}")
    assert isinstance(board, dict)
    rows = board.get("reqTradeSummery") or []
    out = sorted(
        {
            r["symbol"].strip().upper()
            for r in rows
            if isinstance(r, dict) and isinstance(r.get("symbol"), str)
        }
    )
    return out


def local_symbols() -> set[str]:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    return {p.name.split("_")[0] for p in PDF_DIR.glob("*.pdf")}


def collect_new_company_targets(n_companies: int) -> list[dict]:
    """Newest quarterly + annual for the next N companies without local PDFs."""
    have = local_symbols()
    syms = [s for s in live_symbols() if s not in have]
    print(f"Board symbols without local PDFs: {len(syms)} (have {len(have)})")
    targets: list[dict] = []
    companies_done = 0
    seen_urls: set[str] = set()

    for sym in syms:
        if companies_done >= n_companies:
            break
        time.sleep(SLEEP_S)
        try:
            fin = post_json("financials", form=f"symbol={sym}")
        except Exception as exc:
            print(f"  financials fail {sym}: {exc}")
            continue
        if not isinstance(fin, dict):
            continue
        added = 0
        for kind, key in (
            ("quarterly", "infoQuarterlyData"),
            ("annual", "infoAnnualData"),
        ):
            items = fin.get(key) or []
            if not isinstance(items, list) or not items:
                continue
            # newest first
            for item in items[:1]:
                if not isinstance(item, dict):
                    continue
                url = cdn_url(str(item.get("path") or ""))
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                targets.append(
                    {
                        "symbol": sym,
                        "kind": kind,
                        "title": str(item.get("fileText") or kind),
                        "url": url,
                        "id": item.get("id"),
                    }
                )
                added += 1
                break
        if added:
            companies_done += 1
            print(f"  [{companies_done}/{n_companies}] {sym} → +{added} PDF(s) (total {len(targets)})")
    return targets


def download_and_score(meta: dict) -> DlRow:
    row = DlRow(
        symbol=meta["symbol"],
        kind=meta["kind"],
        title=meta["title"],
        url=meta["url"],
        id=meta.get("id"),
    )
    try:
        time.sleep(SLEEP_S)
        data = _request(meta["url"], timeout=120)
        row.bytes = len(data)
        row.download_ok = data[:5] == b"%PDF-" or data[:4] == b"%PDF" or len(data) > 1000
        if not row.download_ok:
            row.error = "not_pdf"
            return row
        PDF_DIR.mkdir(parents=True, exist_ok=True)
        safe = f"{meta['symbol']}_{meta['kind']}_{meta.get('id')}.pdf".replace("/", "_")
        path = PDF_DIR / safe
        path.write_bytes(data)
        row.pdf_path = str(path)

        import fitz

        doc = fitz.open(stream=data, filetype="pdf")
        row.pages = len(doc)
        # Sample early pages for text-ok / metric presence (full extract later)
        parts: list[str] = []
        for i in range(min(40, len(doc))):
            parts.append(doc[i].get_text() or "")
        doc.close()
        text = "\n".join(parts)
        row.chars = len(text)
        row.text_ok = len(text.strip()) >= 400
        # Reuse metric patterns from pdf_eval via simple regexes
        metrics = {
            "revenue": bool(
                re.search(
                    r"\b(revenue|turnover|total\s+income|group\s+revenue|net\s+sales)\b",
                    text,
                    re.I,
                )
            ),
            "profit": bool(
                re.search(
                    r"\b(profit\s+for\s+the\s+(period|year)|net\s+profit|"
                    r"profit\s+attributable|profit\s+after\s+tax|"
                    r"loss\s+for\s+the\s+(period|year))\b",
                    text,
                    re.I,
                )
            ),
            "eps": bool(
                re.search(
                    r"\b(earnings?\s+per\s+share|basic\s+eps|diluted\s+eps|(?<![a-z])EPS(?![a-z])|"
                    r"loss\s+per\s+share)\b",
                    text,
                    re.I,
                )
            ),
        }
        row.metrics_found = metrics
        row.number_hits = len(
            re.findall(r"\(?-?(?:\d{1,3}(?:,\d{3})+|\d{4,})(?:\.\d+)?\)?", text)
        )
        row.scanned_like = (not row.text_ok) or row.chars < 400
    except urllib.error.HTTPError as exc:
        row.error = f"http_{exc.code}"
    except Exception as exc:
        row.error = str(exc)[:240]
    return row


def strong_enough(row: dict) -> bool:
    m = row.get("metrics_found") or {}
    return bool(
        row.get("text_ok")
        and m.get("revenue")
        and m.get("profit")
        and m.get("eps")
        and int(row.get("number_hits") or 0) >= 40
    )


def index_local_pdfs_as_rows() -> list[dict]:
    """Build eval metas from every cached PDF (unique symbol|kind → newest id)."""
    by_key: dict[str, Path] = {}
    for p in PDF_DIR.glob("*.pdf"):
        parts = p.name.split("_")
        if len(parts) < 3:
            continue
        sym = parts[0]
        kind = parts[1]
        if kind not in ("annual", "quarterly"):
            continue
        key = f"{sym}|{kind}"
        prev = by_key.get(key)
        if prev is None or p.stat().st_mtime >= prev.stat().st_mtime:
            by_key[key] = p
    rows: list[dict] = []
    for key, path in sorted(by_key.items()):
        sym, kind = key.split("|", 1)
        # Quick text probe
        try:
            import fitz

            doc = fitz.open(path)
            parts = []
            for i in range(min(40, len(doc))):
                parts.append(doc[i].get_text() or "")
            n_pages = len(doc)
            doc.close()
            text = "\n".join(parts)
            metrics = {
                "revenue": bool(
                    re.search(
                        r"\b(revenue|turnover|total\s+income|net\s+sales)\b", text, re.I
                    )
                ),
                "profit": bool(
                    re.search(
                        r"\b(profit\s+for\s+the\s+(period|year)|net\s+profit|"
                        r"profit\s+attributable|loss\s+for\s+the\s+(period|year))\b",
                        text,
                        re.I,
                    )
                ),
                "eps": bool(
                    re.search(
                        r"\b(earnings?\s+per\s+share|basic\s+eps|loss\s+per\s+share|(?<![a-z])EPS(?![a-z]))\b",
                        text,
                        re.I,
                    )
                ),
            }
            number_hits = len(
                re.findall(r"\(?-?(?:\d{1,3}(?:,\d{3})+|\d{4,})(?:\.\d+)?\)?", text)
            )
            text_ok = len(text.strip()) >= 400
            rows.append(
                {
                    "symbol": sym,
                    "kind": kind,
                    "title": path.name,
                    "url": "",
                    "id": path.stem.split("_")[-1],
                    "text_ok": text_ok,
                    "metrics_found": metrics,
                    "number_hits": number_hits,
                    "pages": n_pages,
                    "pdf_path": str(path),
                    "scanned_like": not text_ok,
                }
            )
        except Exception as exc:
            rows.append(
                {
                    "symbol": sym,
                    "kind": kind,
                    "title": path.name,
                    "url": "",
                    "text_ok": False,
                    "metrics_found": {},
                    "number_hits": 0,
                    "error": str(exc)[:200],
                    "pdf_path": str(path),
                }
            )
    return rows


def detect_unextractable(meta: dict, result_row: dict) -> str | None:
    """Return reason if filing cannot yield reliable text EPS (OCR/image/layout)."""
    if result_row.get("required_ok"):
        return None
    path = meta.get("pdf_path") or ACC.local_pdf_for(meta)
    if not path:
        return "pdf_missing"
    try:
        import fitz

        doc = fitz.open(path)
        sample = "\n".join((doc[i].get_text() or "") for i in range(min(15, len(doc))))
        doc.close()
    except Exception:
        return "read_error"
    low = sample.lower()
    # Severe OCR garble (AFSL-style)
    if re.search(r"inconre|exllellse|protlt|0tlrer|llrte\|e\.st", sample, re.I):
        return "ocr_garble"
    # Annualized-only EPS rows (SDF-style)
    if re.search(r"earnings?\s+per\s+share\s*\(\s*annual", low) or re.search(
        r"basic\s*/\s*diluted\s+earnings?\s+per\s+share\s*\(\s*annual", low
    ):
        # No non-annualized basic/eps number line present
        if not re.search(
            r"(?:basic|earnings?|loss).{0,40}per\s+share(?![^\n]{0,40}annual)",
            sample,
            re.I,
        ):
            return "annualized_eps_only"
    # EPS lines present — if every EPS line is annualized, period EPS is unavailable
    eps_lines = [
        ln
        for ln in sample.splitlines()
        if re.search(r"(earnings?|loss|basic).{0,30}per\s+share|(?<![a-z])eps(?![a-z])", ln, re.I)
    ]
    earning_eps_lines = [
        ln
        for ln in eps_lines
        if re.search(r"earning|basic\s*/\s*dilut|(?<![a-z])eps(?![a-z])|loss\s+per", ln, re.I)
        and not re.search(r"net\s+asset|dividend|market\s+price|nav", ln, re.I)
    ]
    if earning_eps_lines and all(re.search(r"annualis", ln, re.I) for ln in earning_eps_lines):
        return "annualized_eps_only"
    # EPS label present but never followed by a numeric token
    if re.search(r"earnings?\s+per\s+share|loss\s+per\s+share", low) and not re.search(
        r"(?:earnings?|loss|basic).{0,40}per\s+share.{0,30}\(?\-?\d",
        sample,
        re.I | re.S,
    ):
        return "eps_label_without_number"
    fails = result_row.get("fail_reasons") or []
    if "revenue:missing" in fails and (
        True
    ):
        # Classic image-SOPL / sparse statement: chrome without usable revenue cells
        if re.search(r"statement of profit|income statement|revenue", low):
            if "revenue:missing" in fails:
                return "image_or_empty_sopl"
    # Image SOPL: statement page(s) exist but carry almost no tabular amounts
    try:
        import fitz

        doc = fitz.open(path)
        sopl_nums = 0
        sopl_pages = 0
        for i in range(len(doc)):
            t = doc[i].get_text() or ""
            if re.search(r"statement of profit|income statement", t, re.I):
                sopl_pages += 1
                sopl_nums += len(re.findall(r"\d{1,3}(?:,\d{3})+", t))
        doc.close()
        if sopl_pages and sopl_nums < 8:
            return "image_or_empty_sopl"
    except Exception:
        pass
    return None


def eval_extractable(rows: list[dict]) -> dict:
    """Run extractor on strong extractable filings; score vs dual-agree + seed."""
    strong = [r for r in rows if strong_enough(r)]
    # Dedupe symbol|kind
    seen: set[str] = set()
    unique: list[dict] = []
    for r in strong:
        key = f"{r['symbol']}|{r['kind']}"
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)

    print(f"Strong unique filings to extract: {len(unique)}")

    # First-pass extract to quarantine unextractable layouts
    coverage_rows = []
    unextractable: list[dict] = []
    extractable_metas: list[dict] = []
    for meta in unique:
        r = ACC.eval_one(meta)
        row = {
            "symbol": meta["symbol"],
            "kind": meta["kind"],
            "required_ok": r.required_ok,
            "eps": r.eps_basic.value if r.eps_basic else None,
            "eps_label": r.eps_basic.label if r.eps_basic else None,
            "eps_page": r.eps_basic.page if r.eps_basic else None,
            "fail_reasons": r.fail_reasons,
            "error": r.error,
        }
        coverage_rows.append(row)
        reason = detect_unextractable(meta, row)
        if reason and not r.required_ok:
            row["unextractable"] = reason
            unextractable.append(row)
        else:
            extractable_metas.append(meta)

    print(
        f"Extractable={len(extractable_metas)} "
        f"unextractable={len(unextractable)} "
        f"({Counter(u.get('unextractable') for u in unextractable)})"
    )

    gold, build_stats = FEAS.build_expanded_gold(extractable_metas)
    scored = [g for g in gold if g.source in ("human_seed", "dual_agree")]
    eps_score = FEAS.score_extractor_vs_gold(scored) if scored else {
        "n": 0,
        "eps_hits": 0,
        "eps_accuracy_pct": 0.0,
        "rows": [],
    }
    seed = [g for g in gold if g.source == "human_seed"]
    seed_score = FEAS.score_extractor_vs_gold(seed) if seed else {
        "n": 0,
        "eps_hits": 0,
        "eps_accuracy_pct": 0.0,
        "rows": [],
    }

    ok_n = sum(1 for meta in extractable_metas if ACC.eval_one(meta).required_ok)
    misses = [
        r
        for r in coverage_rows
        if not r["required_ok"] and not r.get("unextractable")
    ]
    eps_misses = [r for r in eps_score["rows"] if not r["eps_ok"]]

    alert_sim = FEAS.simulate_alerts(scored) if scored else {
        "n_sims": 0,
        "correct": 0,
        "alert_decision_accuracy_pct": 0.0,
        "rows": [],
    }
    crossing = FEAS.crossing_test(scored) if scored else {
        "n_cross_events": 0,
        "correct": 0,
        "crossing_accuracy_pct": None,
        "events": [],
    }

    coverage_pct = (
        round(100.0 * ok_n / len(extractable_metas), 2) if extractable_metas else 0.0
    )
    perfect = (
        len(extractable_metas) > 0
        and coverage_pct >= 100.0
        and (not scored or eps_score["eps_accuracy_pct"] >= 100.0)
        and (not seed or seed_score["eps_accuracy_pct"] >= 100.0)
        and (not scored or alert_sim["alert_decision_accuracy_pct"] >= 100.0)
        and (
            crossing["crossing_accuracy_pct"] is None
            or crossing["crossing_accuracy_pct"] >= 100.0
        )
        and build_stats.get("disagree", 0) == 0
        and len(misses) == 0
    )

    return {
        "unique_strong": len(unique),
        "extractable_n": len(extractable_metas),
        "unextractable": unextractable,
        "coverage_ok": ok_n,
        "coverage_pct": coverage_pct,
        "gold_build": {k: v for k, v in build_stats.items() if k != "disagreements"},
        "disagreements": build_stats.get("disagreements") or [],
        "scored_n": len(scored),
        "eps_accuracy_pct": eps_score.get("eps_accuracy_pct"),
        "seed_accuracy_pct": seed_score.get("eps_accuracy_pct"),
        "seed_n": seed_score.get("n"),
        "alert_decision_accuracy_pct": alert_sim.get("alert_decision_accuracy_pct"),
        "crossing_accuracy_pct": crossing.get("crossing_accuracy_pct"),
        "crossing_n": crossing.get("n_cross_events"),
        "perfect": perfect,
        "coverage_misses": misses,
        "eps_misses": eps_misses,
        "gold": [asdict(g) for g in gold],
        "coverage_rows": coverage_rows,
        "eps_score_rows": eps_score.get("rows"),
        "alert_sim_misses": alert_sim.get("rows"),
        "crossing": crossing,
    }


def write_report(payload: dict, path: Path) -> None:
    s = payload["summary"]
    lines = [
        "# CSE EPS real-world stress test",
        "",
        f"Generated: `{payload['generated_at']}`  ",
        "Research only — full-board style extract + calc-alert gates.",
        "",
        "## Universe",
        "",
        f"- Live board symbols: **{s['board_symbols']}**",
        f"- Local PDF symbols: **{s['local_symbols']}**",
        f"- Filings indexed: **{s['filings_indexed']}**",
        f"- Text-ok filings: **{s['text_ok']}**",
        f"- Strong (rev+profit+EPS labels): **{s['strong']}**",
        f"- Scanned / text-poor (excluded from extract perfection): **{s['scanned']}**",
        f"- Remaining downloadable companies without PDFs: **{s.get('remaining_companies', '?')}**",
    ]
    no_fin = s.get("remaining_no_financials_on_cse") or []
    if no_fin:
        lines.append(
            "- Board symbols with **no** CSE financial PDFs listed: "
            + ", ".join(f"`{x}`" for x in no_fin)
        )
    lines += [
        "",
        "## Extract + calc-alert gates (strong set)",
        "",
        "| Gate | Result |",
        "|---|---:|",
        f"| Strong unique filings | {s['unique_strong']} |",
        f"| Extractable (text SOPL) | {s.get('extractable_n')} |",
        f"| Unextractable quarantined | {s.get('unextractable_n')} |",
        f"| Coverage on extractable | **{s['coverage_pct']}%** ({s['coverage_ok']}/{s.get('extractable_n')}) |",
        f"| Scored gold EPS accuracy | **{s['eps_accuracy_pct']}%** (n={s['scored_n']}) |",
        f"| Human-seed EPS accuracy | **{s['seed_accuracy_pct']}%** (n={s['seed_n']}) |",
        f"| Alert decision accuracy | **{s['alert_decision_accuracy_pct']}%** |",
        f"| Crossing accuracy | **{s['crossing_accuracy_pct']}%** (n={s['crossing_n']}) |",
        f"| Dual-agree disagreements | {s['disagree']} |",
        f"| Perfect on extractable set? | **{'YES' if s['perfect'] else 'NOT YET'}** |",
        "",
        "## Unextractable (OCR / image SOPL / annualized-only / no EPS number)",
        "",
    ]
    unex = payload.get("unextractable") or []
    if not unex:
        lines.append("- _(none)_")
    for m in unex[:40]:
        lines.append(
            f"- `{m['symbol']}` ({m['kind']}) reason={m.get('unextractable')} "
            f"fails={m.get('fail_reasons')}"
        )
    lines += [
        "",
        "## Coverage misses (extractable — should be empty when perfect)",
        "",
    ]
    misses = payload.get("coverage_misses") or []
    if not misses:
        lines.append("- _(none)_")
    for m in misses[:40]:
        lines.append(
            f"- `{m['symbol']}` ({m['kind']}) fails={m.get('fail_reasons')} "
            f"eps={m.get('eps')} label={m.get('eps_label')!r}"
        )
    lines += ["", "## EPS misses vs scored gold", ""]
    eps_misses = payload.get("eps_misses") or []
    if not eps_misses:
        lines.append("- _(none)_")
    for m in eps_misses[:40]:
        lines.append(
            f"- `{m['symbol']}` ({m['kind']}) gold={m.get('gold_eps')} got={m.get('got_eps')} "
            f"src={m.get('gold_source')}"
        )
    lines += [
        "",
        "## Disagreements (excluded from scored gold)",
        "",
    ]
    disag = payload.get("disagreements") or []
    if not disag:
        lines.append("- _(none)_")
    for d in disag[:40]:
        lines.append(
            f"- `{d['symbol']}` ({d['kind']}) main={d.get('main_eps')} "
            f"indep={d.get('indep_eps')} main_label={d.get('main_label')!r}"
        )
    lines += ["", f"Raw: `{payload['json_name']}`", ""]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def companies_without_downloadable_financials() -> list[str]:
    """Board symbols that have no quarterly/annual PDF rows on cse.lk."""
    have = local_symbols()
    missing = [s for s in live_symbols() if s not in have]
    empty: list[str] = []
    for sym in missing:
        time.sleep(SLEEP_S)
        try:
            fin = post_json("financials", form=f"symbol={sym}")
        except Exception:
            empty.append(sym)
            continue
        if not isinstance(fin, dict):
            empty.append(sym)
            continue
        q = fin.get("infoQuarterlyData") or []
        a = fin.get("infoAnnualData") or []
        if (isinstance(q, list) and q) or (isinstance(a, list) and a):
            continue
        empty.append(sym)
    return empty


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--companies",
        type=int,
        default=100,
        help="How many new companies to download (0 = none)",
    )
    ap.add_argument("--eval-only", action="store_true")
    ap.add_argument(
        "--require-perfect",
        action="store_true",
        help="Exit 2 if strong-set gates are not all 100%",
    )
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)

    board = live_symbols()
    dl_rows: list[DlRow] = []
    if not args.eval_only and args.companies > 0:
        targets = collect_new_company_targets(args.companies)
        print(f"Downloading {len(targets)} PDFs…")
        for i, meta in enumerate(targets, 1):
            print(f"[{i}/{len(targets)}] {meta['symbol']} {meta['kind']} …", flush=True)
            row = download_and_score(meta)
            dl_rows.append(row)
            status = "ok" if row.text_ok else ("scanned" if row.download_ok else "fail")
            print(
                f"  → {status} pages={row.pages} chars={row.chars} "
                f"metrics={row.metrics_found} err={row.error}"
            )

    print("Indexing local PDF cache…")
    indexed = index_local_pdfs_as_rows()
    text_ok = sum(1 for r in indexed if r.get("text_ok"))
    strong = sum(1 for r in indexed if strong_enough(r))
    scanned = sum(1 for r in indexed if r.get("scanned_like"))

    print(f"Indexed={len(indexed)} text_ok={text_ok} strong={strong} scanned={scanned}")
    result = eval_extractable(indexed)

    # Persist expanded gold from this run
    gold_path = OUT_DIR / "cse_financial_eps_gold_expanded.json"
    gold_path.write_text(json.dumps(result["gold"], indent=2), encoding="utf-8")

    no_fin = companies_without_downloadable_financials()
    remaining_raw = max(0, len(board) - len(local_symbols()))
    remaining_downloadable = max(0, remaining_raw - len(no_fin))
    summary = {
        "board_symbols": len(board),
        "local_symbols": len(local_symbols()),
        "filings_indexed": len(indexed),
        "text_ok": text_ok,
        "strong": strong,
        "scanned": scanned,
        "downloaded_this_run": len(dl_rows),
        "download_text_ok": sum(1 for r in dl_rows if r.text_ok),
        "unique_strong": result["unique_strong"],
        "extractable_n": result.get("extractable_n"),
        "unextractable_n": len(result.get("unextractable") or []),
        "coverage_ok": result["coverage_ok"],
        "coverage_pct": result["coverage_pct"],
        "scored_n": result["scored_n"],
        "eps_accuracy_pct": result["eps_accuracy_pct"],
        "seed_accuracy_pct": result["seed_accuracy_pct"],
        "seed_n": result["seed_n"],
        "alert_decision_accuracy_pct": result["alert_decision_accuracy_pct"],
        "crossing_accuracy_pct": result["crossing_accuracy_pct"],
        "crossing_n": result["crossing_n"],
        "disagree": result["gold_build"].get("disagree", 0),
        "perfect": result["perfect"],
        "remaining_companies": remaining_downloadable,
        "remaining_no_financials_on_cse": no_fin,
    }
    print("SUMMARY", json.dumps(summary, indent=2))

    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    json_name = f"cse_eps_realworld_stress_{ts}.json"
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "summary": summary,
        "download_rows": [asdict(r) for r in dl_rows],
        "gold_build": result["gold_build"],
        "disagreements": result["disagreements"],
        "unextractable": result.get("unextractable") or [],
        "coverage_misses": result["coverage_misses"],
        "eps_misses": result["eps_misses"],
        "coverage_rows": result["coverage_rows"],
        "eps_score_rows": result["eps_score_rows"],
        "json_name": json_name,
    }
    (OUT_DIR / json_name).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_report(payload, OUT_DIR / "CSE_EPS_REALWORLD_STRESS.md")
    print(f"Wrote {OUT_DIR / json_name}")
    print(f"Perfect? {'YES' if result['perfect'] else 'NOT YET'}")
    print(
        f"Remaining downloadable companies without PDFs: {summary['remaining_companies']}"
    )
    if summary.get("remaining_no_financials_on_cse"):
        print(
            "No CSE financial PDFs listed for: "
            + ", ".join(summary["remaining_no_financials_on_cse"])
        )

    if args.require_perfect and not result["perfect"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
