#!/usr/bin/env python3
"""EPS calc-alert feasibility — prove (or falsify) `/alert SYMBOL eps above X`.

Semantics under test (v1 candidate):
  - Metric: **basic EPS** (diluted stored but alert defaults to basic)
  - Period: **current quarter** for quarterlies; **annual year** for annuals
  - Entity: **Group** when both Group + Company exist
  - Trigger: on *new filing extract*, if eps crosses user threshold (above/below)
  - Fire once per (rule, filing_id); not continuous price-style polling

This is research-only until gold accuracy ≥ target. Not wired into the bot.

Usage:
  python3 scripts/experiments/cse_eps_calc_alert_feasibility.py
  python3 scripts/experiments/cse_eps_calc_alert_feasibility.py --target 0.99
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from importlib.machinery import SourceFileLoader
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT_DIR = REPO / "docs" / "experiments"
PDF_DIR = Path("/tmp/cse-financial-pdfs")
ACC = SourceFileLoader(
    "cse_acc",
    str(REPO / "scripts" / "experiments" / "cse_financial_accuracy_eval.py"),
).load_module()

# Existing hand gold (seed)
SEED_GOLD = OUT_DIR / "cse_financial_gold_labels.json"


@dataclass
class GoldEps:
    symbol: str
    kind: str
    eps_basic: float
    eps_diluted: float | None
    revenue: float | None
    profit: float | None
    page: int
    label: str
    source: str  # human_seed | dual_agree | human_resolved
    notes: list[str] = field(default_factory=list)


@dataclass
class AlertSim:
    symbol: str
    kind: str
    rule: str  # eps_above | eps_below
    threshold: float
    gold_eps: float
    extracted_eps: float | None
    should_fire: bool  # based on gold
    did_fire: bool  # based on extract
    correct: bool
    fail_reason: str | None = None


def _page_band(text: str, n: int = 25) -> str:
    return "\n".join(text.splitlines()[:n]).lower()


def _is_quarter_page(text: str) -> bool:
    head = _page_band(text)
    return bool(
        re.search(
            r"for\s+the\s+(?:three\s+months|quarter)\s+ended|three\s+months\s+ended",
            head,
        )
    )


def _is_ytd_page(text: str) -> bool:
    head = _page_band(text)
    if _is_quarter_page(text):
        return False
    return bool(
        re.search(
            r"for\s+the\s+(?:period|six\s+months|nine\s+months|year)\s+ended",
            head,
        )
    )


def _is_group_page(text: str) -> bool:
    return bool(re.search(r"\bgroup\b", _page_band(text)))


def _is_company_only(text: str) -> bool:
    head = _page_band(text)
    return bool(re.search(r"\bcompany\b", head)) and not bool(
        re.search(r"\bgroup\b", head)
    )


def _is_notes_or_restatement_page(text: str) -> bool:
    head = "\n".join(text.splitlines()[:30]).lower()
    return bool(
        re.search(
            r"notes?\s+to\s+the\s+financial|as\s+previously\s+reported|"
            r"cumulative\s+impact\s+of\s+adjustments|restated\s+balance|"
            r"corporate\s+information|basis\s+of\s+preparation|"
            r"computation\s+of\s+the\s+basic\s+earnings",
            head,
        )
    )


def _is_sopl(text: str) -> bool:
    low = text.lower()
    if _is_notes_or_restatement_page(text):
        return False
    head = "\n".join(text.splitlines()[:30]).lower()
    # Highlights / ratio / "income statement data" summary tables ≠ primary SOPL
    if re.search(
        r"financial\s+highlights|income\s+statement\s+data|"
        r"price\s+earnings|earnings\s+yield|earnings\s+highlights|"
        r"^\s*contents\b|about\s+this\s+report",
        head,
    ) and "statement of profit" not in low:
        return False
    if re.search(r"price\s+earnings|earnings\s+yield|earnings\s+highlights", low):
        # Investor highlights / ratio pages are not the primary SOPL
        if "statement of profit" not in low and "income statement" not in low:
            return False
    return (
        "statement of profit" in low
        or (
            "income statement" in low
            and not re.search(r"income\s+statement\s+data", low)
            and bool(re.search(r"\brevenue\b|\bturnover\b|interest\s+income", low))
        )
        or (
            "profit or loss" in low
            and "earnings per share" in low
            and bool(
                re.search(
                    r"\brevenue\b|\bturnover\b|interest\s+income|"
                    r"gross\s+income|gross\s+written",
                    low,
                )
            )
            and len(text) > 1200
        )
    )


def pick_canonical_pages(
    pdf_path: Path, *, kind: str
) -> list[tuple[int, str, dict[str, bool]]]:
    """Return candidate SOPL pages with flags, best-first."""
    max_pages = None if kind == "annual" else 50
    scored = ACC.score_pages(pdf_path, max_pages=max_pages)
    out: list[tuple[int, str, dict[str, bool]]] = []
    for page, hits, text in scored:
        if hits < 2 and not _is_sopl(text):
            continue
        flags = {
            "sopl": _is_sopl(text),
            "quarter": _is_quarter_page(text),
            "ytd": _is_ytd_page(text),
            "group": _is_group_page(text),
            "company_only": _is_company_only(text),
        }
        score = hits
        if flags["sopl"]:
            score += 10
        if kind == "quarterly":
            if flags["quarter"]:
                score += 20
            if flags["ytd"]:
                score -= 15
        if flags["group"]:
            score += 5
        if flags["company_only"]:
            score -= 4
        out.append((score, page, text, flags))
    out.sort(key=lambda x: (-x[0], x[1]))
    return [(p, t, f) for _, p, t, f in out[:12]]


def independent_eps_from_page(text: str, page: int) -> GoldEps | None:
    """Second-path EPS reader used to build/agree gold (not the main ranker)."""
    lines = ACC._stitch_broken_parens(
        [ln.strip() for ln in text.splitlines() if ln.strip()]
    )
    best: tuple[int, float, str, float | None] | None = None
    # Walk for basic / combined / loss-per-share
    i = 0
    while i < len(lines):
        ln = lines[i]
        cls = ACC._classify(ln)
        label = ln
        bucket = cls
        if cls == "eps_generic" and i + 1 < len(lines):
            tag = ACC._classify(lines[i + 1])
            if tag in ("eps_basic_tag", "eps_basic"):
                bucket = "eps_basic"
                label = f"{ln} {lines[i+1]}"
                collect_idx = i + 1
            elif tag in ("eps_diluted_tag", "eps_diluted"):
                bucket = "eps_diluted"
                label = f"{ln} {lines[i+1]}"
                collect_idx = i + 1
            elif tag in ("eps_combined", "eps_combined_tag") or re.search(
                r"basic\s*/\s*di|basic\s+and\s+di", lines[i + 1], re.I
            ):
                bucket = "eps_combined"
                label = f"{ln} {lines[i+1]}"
                collect_idx = i + 1
            else:
                collect_idx = i
        else:
            collect_idx = i
        if bucket not in (
            "eps_basic",
            "eps_combined",
            "eps_generic",
            "eps_diluted",
        ):
            i += 1
            continue
        low = label.lower()
        # Mirror main-extractor skips for independent path
        if re.search(r"annualised|annualized|\(usd\)|usd\)|continuing|discontinued", low):
            i += 1
            continue
        if re.search(r"before\s+sub-?division", low):
            i += 1
            continue
        if re.search(r"vs\s+\(?\s*lkr|compared\s+to|has been calculated|for all periods", low):
            i += 1
            continue
        if len(label) > 100:
            i += 1
            continue
        nums = ACC._collect_following_nums(lines, collect_idx, eps_mode=True)
        if not nums:
            i += 1
            continue
        raw, val = nums[0]
        if abs(val) > 5000:
            i += 1
            continue
        # Years / page numbers mistaken as EPS
        if val == int(val) and 1900 <= abs(val) <= 2100:
            i += 1
            continue
        rank = 0
        if bucket == "eps_basic":
            rank = 5
        elif bucket == "eps_combined":
            rank = 4
        elif bucket == "eps_generic":
            rank = 2
        elif bucket == "eps_diluted":
            rank = 1
        if "loss per share" in low:
            rank = 5
        if "for the period" in low:
            rank += 3
        if "after share" in low or "after share split" in low or "after sub-division" in low or "after subdivision" in low:
            rank += 4
        if "after share split" in low:
            rank += 3
        if re.search(r"per\s+share\s+before|before\s*$|before\s+share", low):
            rank -= 4
        if "continuing" in low or "discontinued" in low:
            rank -= 2
        if "before sub-division" in low or "before subdivision" in low:
            rank -= 3
        if "after sub-division" in low or "after subdivision" in low:
            rank += 2
        if best is None or rank > best[0]:
            dil = None
            if bucket in ("eps_combined",) or "basic / dil" in low or "basic and dil" in low:
                dil = val
            best = (rank, val, label[:120], dil)
        i += 1
    if not best:
        return None
    _, eps, label, dil = best
    return GoldEps(
        symbol="",
        kind="",
        eps_basic=eps,
        eps_diluted=dil,
        revenue=None,
        profit=None,
        page=page,
        label=label,
        source="page_independent",
        notes=[],
    )


def independent_rev_pat(text: str) -> tuple[float | None, float | None]:
    lines = ACC._stitch_broken_parens(
        [ln.strip() for ln in text.splitlines() if ln.strip()]
    )
    rev = pat = None
    for i, ln in enumerate(lines):
        cls = ACC._classify(ln)
        if cls not in ("revenue", "profit"):
            continue
        nums = ACC._collect_following_nums(lines, i, eps_mode=False)
        if not nums:
            continue
        if cls == "revenue" and rev is None:
            rev = nums[0][1]
        if cls == "profit" and pat is None:
            # prefer for-the-period
            if "for the period" in ln.lower() or "after tax" in ln.lower() or pat is None:
                if "before" in ln.lower() and "after" not in ln.lower():
                    continue
                pat = nums[0][1]
    return rev, pat


def build_expanded_gold(strong: list[dict]) -> tuple[list[GoldEps], dict]:
    seed = {
        (g["symbol"], g["kind"]): g
        for g in json.loads(SEED_GOLD.read_text())
    }
    gold: list[GoldEps] = []
    stats = {
        "n": 0,
        "seed": 0,
        "dual_agree": 0,
        "disagree": 0,
        "extractor_only": 0,
        "independent_only": 0,
        "both_miss": 0,
        "unresolved_excluded": 0,
        "disagreements": [],
    }

    for meta in strong:
        stats["n"] += 1
        key = (meta["symbol"], meta["kind"])
        path = ACC.local_pdf_for(meta)
        if path is None:
            stats["both_miss"] += 1
            continue

        # Main extractor
        main = ACC.eval_one(meta)

        # Independent path on canonical pages
        pages = pick_canonical_pages(path, kind=meta["kind"])
        indep: GoldEps | None = None
        for page, text, flags in pages:
            if meta["kind"] == "quarterly" and flags["ytd"] and not flags["quarter"]:
                continue
            # Skip quarterly-analysis / highlights / notes-restatement pages
            head = "\n".join(text.splitlines()[:25]).lower()
            low = text.lower()
            if _is_notes_or_restatement_page(text):
                continue
            if re.search(
                r"indicative\s+us\s*dollar|us\s*dollar\s+income|"
                r"income\s+statement\s+in\s+usd|\bin\s+us\s*dollars\b",
                head,
            ):
                continue
            if re.search(
                r"financial\s+highlights|income\s+statement\s+data|"
                r"quarterly\s+analysis|table\s+of\s+contents|price\s+earnings|"
                r"earnings\s+yield|earnings\s+highlights",
                head,
            ) and not (
                "statement of profit" in low and "revenue" in low and len(text) > 1500
            ):
                continue
            if re.search(r"price\s+earnings\s+ratio|earnings\s+yield", text.lower()) and not (
                "statement of profit" in text.lower() and "revenue" in text.lower()
            ):
                continue
            if meta["kind"] == "quarterly":
                has_period = bool(
                    re.search(r"profit\s+for\s+the\s+period|loss\s+for\s+the\s+period", low)
                )
                has_year_only = bool(
                    re.search(r"profit\s+for\s+the\s+year|loss\s+for\s+the\s+year", low)
                ) and not has_period
                if has_year_only:
                    continue
            cand = independent_eps_from_page(text, page)
            if cand is None:
                continue
            rev, pat = independent_rev_pat(text)
            cand.symbol = meta["symbol"]
            cand.kind = meta["kind"]
            cand.revenue = rev
            cand.profit = pat
            cand.notes = [k for k, v in flags.items() if v]
            # Prefer first matching canonical page (already sorted)
            indep = cand
            break

        if key in seed:
            g = seed[key]
            gold.append(
                GoldEps(
                    symbol=meta["symbol"],
                    kind=meta["kind"],
                    eps_basic=float(g["eps_basic"]),
                    eps_diluted=float(g["eps_diluted"]) if g.get("eps_diluted") is not None else None,
                    revenue=float(g["revenue"]) if g.get("revenue") is not None else None,
                    profit=float(g["profit"]) if g.get("profit") is not None else None,
                    page=-1,
                    label="seed",
                    source="human_seed",
                )
            )
            stats["seed"] += 1
            continue

        if (
            main.required_ok
            and indep is not None
            and abs(main.eps_basic.value - indep.eps_basic) < 0.06
        ):
            # Dual agreement → accept as gold
            gold.append(
                GoldEps(
                    symbol=meta["symbol"],
                    kind=meta["kind"],
                    eps_basic=main.eps_basic.value,
                    eps_diluted=main.eps_diluted.value if main.eps_diluted else indep.eps_diluted,
                    revenue=main.revenue.value if main.revenue else indep.revenue,
                    profit=main.profit.value if main.profit else indep.profit,
                    page=main.eps_basic.page,
                    label=main.eps_basic.label,
                    source="dual_agree",
                    notes=["main_indep_eps_agree"],
                )
            )
            stats["dual_agree"] += 1
            continue

        if main.required_ok and indep is not None:
            stats["disagree"] += 1
            stats["disagreements"].append(
                {
                    "symbol": meta["symbol"],
                    "kind": meta["kind"],
                    "main_eps": main.eps_basic.value if main.eps_basic else None,
                    "main_label": main.eps_basic.label if main.eps_basic else None,
                    "main_page": main.eps_basic.page if main.eps_basic else None,
                    "indep_eps": indep.eps_basic,
                    "indep_label": indep.label,
                    "indep_page": indep.page,
                    "indep_flags": indep.notes,
                }
            )
            # Do NOT auto-promote disagreements into gold — that circularly
            # inflates accuracy. Leave them out of the scored set.
            stats["unresolved_excluded"] = stats.get("unresolved_excluded", 0) + 1
            continue

        if main.required_ok and indep is None:
            stats["extractor_only"] += 1
            # Extractor-only is useful for coverage but not for accuracy truth.
            # Keep in expanded file as reference, excluded from scored gates below.
            gold.append(
                GoldEps(
                    symbol=meta["symbol"],
                    kind=meta["kind"],
                    eps_basic=main.eps_basic.value,
                    eps_diluted=main.eps_diluted.value if main.eps_diluted else None,
                    revenue=main.revenue.value if main.revenue else None,
                    profit=main.profit.value if main.profit else None,
                    page=main.eps_basic.page,
                    label=main.eps_basic.label,
                    source="extractor_only",
                    notes=["no_indep", "excluded_from_accuracy_gate"],
                )
            )
            continue

        if indep is not None and not main.required_ok:
            stats["independent_only"] += 1
            gold.append(
                GoldEps(
                    symbol=meta["symbol"],
                    kind=meta["kind"],
                    eps_basic=indep.eps_basic,
                    eps_diluted=indep.eps_diluted,
                    revenue=indep.revenue,
                    profit=indep.profit,
                    page=indep.page,
                    label=indep.label,
                    source="independent_only",
                    notes=indep.notes,
                )
            )
            continue

        stats["both_miss"] += 1

    return gold, stats


def score_extractor_vs_gold(gold: list[GoldEps]) -> dict:
    hits = 0
    rows = []
    for g in gold:
        r = ACC.eval_one({"symbol": g.symbol, "kind": g.kind, "title": "", "url": ""})
        ok = bool(
            r.required_ok
            and r.eps_basic
            and abs(r.eps_basic.value - g.eps_basic) < 0.05
        )
        # Also check rev/pat when gold has them (looser — secondary)
        rev_ok = True
        pat_ok = True
        if g.revenue is not None and r.revenue:
            rev_ok = abs(r.revenue.value - g.revenue) / max(abs(g.revenue), 1) < 0.01
        if g.profit is not None and r.profit:
            pat_ok = abs(r.profit.value - g.profit) / max(abs(g.profit), 1) < 0.01
        hits += int(ok)
        rows.append(
            {
                "symbol": g.symbol,
                "kind": g.kind,
                "gold_source": g.source,
                "eps_ok": ok,
                "rev_ok": rev_ok,
                "pat_ok": pat_ok,
                "gold_eps": g.eps_basic,
                "got_eps": r.eps_basic.value if r.eps_basic else None,
                "got_label": r.eps_basic.label if r.eps_basic else None,
            }
        )
    n = len(gold)
    return {
        "n": n,
        "eps_hits": hits,
        "eps_accuracy_pct": round(100.0 * hits / n, 2) if n else 0.0,
        "strict_seed_only_pct": None,  # filled below
        "rows": rows,
    }


def simulate_alerts(gold: list[GoldEps]) -> dict:
    """Simulate eps above/below rules around each gold EPS."""
    sims: list[AlertSim] = []
    for g in gold:
        r = ACC.eval_one({"symbol": g.symbol, "kind": g.kind, "title": "", "url": ""})
        extracted = r.eps_basic.value if r.eps_basic else None
        # Build 4 synthetic thresholds per filing
        cases = [
            ("eps_above", g.eps_basic - 0.01, True),   # should fire
            ("eps_above", g.eps_basic + abs(g.eps_basic) * 0.5 + 1.0, False),  # should not
            ("eps_below", g.eps_basic + 0.01, True),
            ("eps_below", g.eps_basic - abs(g.eps_basic) * 0.5 - 1.0, False),
        ]
        for rule, thr, should in cases:
            if extracted is None:
                did = False
                correct = False
                reason = "extract_missing"
            else:
                did = extracted > thr if rule == "eps_above" else extracted < thr
                # Correct fire decision vs gold truth
                should_real = g.eps_basic > thr if rule == "eps_above" else g.eps_basic < thr
                correct = did == should_real and abs(extracted - g.eps_basic) < 0.05
                reason = None if correct else (
                    "wrong_eps_value" if abs(extracted - g.eps_basic) >= 0.05 else "logic_bug"
                )
            sims.append(
                AlertSim(
                    symbol=g.symbol,
                    kind=g.kind,
                    rule=rule,
                    threshold=thr,
                    gold_eps=g.eps_basic,
                    extracted_eps=extracted,
                    should_fire=should,
                    did_fire=did,
                    correct=correct,
                    fail_reason=reason,
                )
            )
    n = len(sims)
    ok = sum(1 for s in sims if s.correct)
    return {
        "n_sims": n,
        "correct": ok,
        "alert_decision_accuracy_pct": round(100.0 * ok / n, 2) if n else 0.0,
        "false_fires": sum(1 for s in sims if s.did_fire and not s.should_fire and s.fail_reason),
        "missed_fires": sum(1 for s in sims if (not s.did_fire) and s.should_fire and s.fail_reason),
        "rows": [asdict(s) for s in sims if not s.correct][:40],
    }


def crossing_test(gold: list[GoldEps]) -> dict:
    """True calc-alert path: prev filing EPS → new filing EPS crosses threshold."""
    # Group by symbol; need ≥2 filings (quarterly+annual or two kinds)
    by_sym: dict[str, list[GoldEps]] = {}
    for g in gold:
        by_sym.setdefault(g.symbol, []).append(g)

    events = []
    for sym, items in by_sym.items():
        if len(items) < 2:
            continue
        # Sort annual after quarterly as "newer" proxy is weak; just pair kinds
        a, b = items[0], items[1]
        # threshold between the two EPS values
        lo, hi = sorted([a.eps_basic, b.eps_basic])
        if abs(hi - lo) < 1e-6:
            continue
        thr = (lo + hi) / 2.0
        # Simulate: old=a, new=b, rule eps_above thr
        for old, new in ((a, b), (b, a)):
            r_new = ACC.eval_one(
                {"symbol": new.symbol, "kind": new.kind, "title": "", "url": ""}
            )
            got = r_new.eps_basic.value if r_new.eps_basic else None
            bool(got is not None and got > thr)
            # Only count "crossing" cases
            if not (new.eps_basic > thr and old.eps_basic <= thr) and not (
                new.eps_basic <= thr and old.eps_basic > thr
            ):
                continue
            # above-cross
            should_above = old.eps_basic <= thr < new.eps_basic
            did_above = got is not None and old.eps_basic <= thr < got
            # Use gold old for previous; extract for new
            events.append(
                {
                    "symbol": sym,
                    "old": {"kind": old.kind, "eps": old.eps_basic},
                    "new": {"kind": new.kind, "gold_eps": new.eps_basic, "got_eps": got},
                    "threshold": thr,
                    "should_fire_above": should_above,
                    "did_fire_above": did_above,
                    "correct": should_above == did_above
                    and got is not None
                    and abs(got - new.eps_basic) < 0.05,
                }
            )
    ok = sum(1 for e in events if e["correct"])
    n = len(events)
    return {
        "n_cross_events": n,
        "correct": ok,
        "crossing_accuracy_pct": round(100.0 * ok / n, 2) if n else None,
        "events": events,
    }


def write_report(payload: dict, path: Path) -> None:
    s = payload["summary"]
    lines = [
        "# EPS calc-alert feasibility (`/alert SYMBOL eps above X`)",
        "",
        f"Generated: `{payload['generated_at']}`  ",
        "Research only — proves whether calc alerts are *possible* at high accuracy.",
        "",
        "## Alert semantics under test",
        "",
        "1. **Metric:** basic EPS (default); diluted stored separately",
        "2. **Period:** current quarter (quarterlies) / full year (annuals)",
        "3. **Entity:** Group preferred over Company-only",
        "4. **Trigger:** new filing extract vs user threshold (not live price poll)",
        "5. **Dedupe:** one fire per `(rule_id, filing_id)`",
        "",
        "## Results",
        "",
        "| Gate | Result |",
        "|---|---:|",
        f"| Human+dual scored gold | {s['scored_gold_n']} (of {s['gold_n']} listed) |",
        f"| EPS accuracy vs scored gold | **{s['eps_accuracy_pct']}%** |",
        f"| Seed human gold (strict) | **{s['seed_accuracy_pct']}%** ({s['seed_hits']}/{s['seed_n']}) |",
        f"| Dual-agree subset | **{s.get('dual_accuracy_pct')}%** ({s.get('dual_hits')}/{s.get('dual_n')}) |",
        f"| Synthetic threshold decision accuracy | **{s['alert_decision_accuracy_pct']}%** |",
        f"| Filing→filing crossing accuracy | **{s.get('crossing_accuracy_pct')}%** "
        f"({s.get('crossing_correct')}/{s.get('crossing_n')}) |",
        f"| Unresolved disagreements excluded | {s.get('unresolved_excluded', 0)} |",
        f"| Target | {payload['target']*100:.0f}% |",
        f"| Feasible at target? | **{'YES' if s['feasible'] else 'NOT YET'}** |",
        "",
        "### Gold construction",
        "",
        "```json",
        json.dumps(payload["gold_build_stats"], indent=2),
        "```",
        "",
        "Accuracy gates use **human_seed + dual_agree only**. "
        "`extractor_only` rows are listed for coverage but excluded from the "
        "accuracy denominator. Disagreements are excluded until human-labeled.",
        "",
        "## Path to bot implementation (only if feasible)",
        "",
        "1. Migration: `filing_metrics` + `alert_rules.type` in (`eps_above`,`eps_below`)",
        "2. Job: on new `financials` PDF for watched symbols → extract → gate → store",
        "3. Rule eval: compare new `eps_basic` to threshold; fire Telegram once per filing",
        "4. Message must include: EPS, period, scale, Group/Company, PDF link, NFA",
        "5. Fail closed: if extract gates fail, **do not fire**, notify ops/log only",
        "6. Expand human gold to ≥50 before production flag flip",
        "",
        "## Still blocked for production if",
        "",
        "- Human-seed EPS accuracy < 99%",
        "- Unresolved disagreement cluster grows",
        "- No filing-id dedupe / no scale tag in message",
        "",
        f"Raw: `{payload['json_name']}`",
        "",
    ]
    # Show misses
    misses = [r for r in payload["eps_score"]["rows"] if not r["eps_ok"]]
    lines += ["## EPS misses vs gold", ""]
    if not misses:
        lines.append("- _(none)_")
    for r in misses[:20]:
        lines.append(
            f"- `{r['symbol']}` ({r['kind']}) gold={r['gold_eps']} got={r['got_eps']} "
            f"src={r['gold_source']} label={r.get('got_label')!r}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=float, default=0.99)
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    prior = sorted(OUT_DIR.glob("cse_financial_pdf_eval_*.json"))[-1]
    strong = ACC.load_strong_rows(prior)
    print(f"Strong unique filings: {len(strong)}")

    gold, build_stats = build_expanded_gold(strong)
    print("Gold build:", json.dumps({k: v for k, v in build_stats.items() if k != "disagreements"}, indent=2))
    if build_stats["disagreements"]:
        print(f"Disagreements: {len(build_stats['disagreements'])}")
        for d in build_stats["disagreements"][:8]:
            print(" ", d)

    # Persist expanded gold
    gold_path = OUT_DIR / "cse_financial_eps_gold_expanded.json"
    gold_path.write_text(
        json.dumps([asdict(g) for g in gold], indent=2),
        encoding="utf-8",
    )

    # Non-circular gold: human seed + dual-agree only (exclude extractor_only)
    scored_gold = [g for g in gold if g.source in ("human_seed", "dual_agree")]
    eps_score = score_extractor_vs_gold(scored_gold)
    # Strict seed-only (highest-trust gate)
    seed_gold = [g for g in gold if g.source == "human_seed"]
    seed_score = score_extractor_vs_gold(seed_gold)
    seed_rows = seed_score["rows"]
    seed_hits = sum(1 for r in seed_rows if r["eps_ok"])
    seed_n = len(seed_rows)
    dual_rows = [r for r in eps_score["rows"] if r["gold_source"] == "dual_agree"]
    dual_hits = sum(1 for r in dual_rows if r["eps_ok"])
    dual_n = len(dual_rows)

    alert_sim = simulate_alerts(scored_gold)
    crossing = crossing_test(scored_gold)

    seed_ok = seed_n > 0 and seed_hits / seed_n >= args.target
    scored_ok = (
        len(scored_gold) > 0
        and eps_score["eps_accuracy_pct"] / 100.0 >= args.target
    )
    alert_ok = alert_sim["alert_decision_accuracy_pct"] / 100.0 >= args.target
    cross_ok = (
        crossing["crossing_accuracy_pct"] is None
        or crossing["crossing_accuracy_pct"] / 100.0 >= args.target
    )
    # Require human seed panel ≥10 and pass all non-circular gates
    feasible = seed_ok and scored_ok and alert_ok and cross_ok and seed_n >= 10

    summary = {
        "gold_n": len(gold),
        "scored_gold_n": len(scored_gold),
        "eps_accuracy_pct": eps_score["eps_accuracy_pct"],
        "seed_n": seed_n,
        "seed_hits": seed_hits,
        "seed_accuracy_pct": round(100.0 * seed_hits / seed_n, 2) if seed_n else None,
        "dual_n": dual_n,
        "dual_hits": dual_hits,
        "dual_accuracy_pct": round(100.0 * dual_hits / dual_n, 2) if dual_n else None,
        "alert_decision_accuracy_pct": alert_sim["alert_decision_accuracy_pct"],
        "crossing_n": crossing["n_cross_events"],
        "crossing_correct": crossing["correct"],
        "crossing_accuracy_pct": crossing["crossing_accuracy_pct"],
        "unresolved_excluded": build_stats.get("unresolved_excluded", 0),
        "feasible": feasible,
    }
    print("SUMMARY", json.dumps(summary, indent=2))

    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    json_name = f"cse_eps_calc_alert_feasibility_{ts}.json"
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "target": args.target,
        "semantics": {
            "metric": "basic_eps",
            "period": "current_quarter_or_annual",
            "entity": "group_preferred",
            "trigger": "new_filing_extract",
        },
        "summary": summary,
        "gold_build_stats": {
            k: v for k, v in build_stats.items() if k != "disagreements"
        },
        "disagreements": build_stats["disagreements"],
        "eps_score": eps_score,
        "alert_sim": alert_sim,
        "crossing": crossing,
        "json_name": json_name,
    }
    (OUT_DIR / json_name).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_report(payload, OUT_DIR / "CSE_EPS_CALC_ALERT_FEASIBILITY.md")
    print(f"Wrote {OUT_DIR / json_name}")
    print(f"Feasible@≥{args.target:.0%}: {'YES' if feasible else 'NOT YET'}")
    if not feasible:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
