#!/usr/bin/env python3
"""YoY pairing harness over local CSE financial PDF cache (research).

Usage:
  python3 scripts/experiments/cse_filing_yoy_pairing.py
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from koel.extractors.financial_pdf import extract_filing_from_path, infer_filing_kind
from koel.metrics.compare import MetricsRow, resolve_prior

REPO = Path(__file__).resolve().parents[2]
PDF_DIR = Path("/tmp/cse-financial-pdfs")
OUT = REPO / "docs" / "experiments"


def main() -> None:
    if not PDF_DIR.exists():
        print(f"No PDF cache at {PDF_DIR}")
        raise SystemExit(1)

    by_sym_kind: dict[tuple[str, str], list[MetricsRow]] = defaultdict(list)
    n = 0
    for path in sorted(PDF_DIR.glob("*.pdf")):
        # SYMBOL_kind_id.pdf
        parts = path.name.split("_")
        if len(parts) < 2:
            continue
        symbol = parts[0]
        kind = parts[1] if parts[1] in ("quarterly", "annual") else infer_filing_kind(title=path.name)
        if kind not in ("quarterly", "annual"):
            continue
        n += 1
        result = extract_filing_from_path(path, kind=kind, title=path.name)
        row = MetricsRow(
            id=n,
            symbol=symbol,
            kind=result.kind if result.kind in ("quarterly", "annual") else kind,
            fiscal_period_end=result.fiscal_period_end,
            fiscal_quarter=result.fiscal_quarter,
            entity=result.entity,
            scale=result.scale,
            currency=result.currency,
            revenue=result.revenue,
            profit=result.profit,
            eps_basic=result.eps_basic,
            extract_ok=result.extract_ok,
        )
        by_sym_kind[(symbol, row.kind)].append(row)

    pairable = 0
    paired = 0
    qualities: dict[str, int] = defaultdict(int)
    samples: list[dict] = []
    for (symbol, kind), rows in sorted(by_sym_kind.items()):
        ok_rows = [r for r in rows if r.extract_ok and r.fiscal_period_end]
        if len(ok_rows) < 2:
            continue
        pairable += 1
        # newest vs rest
        ok_rows.sort(key=lambda r: r.fiscal_period_end or datetime.min.date(), reverse=True)
        current = ok_rows[0]
        cmp = resolve_prior(current, ok_rows[1:])
        qualities[cmp.match_quality] += 1
        if cmp.match_quality in ("exact_yoy", "approx_yoy"):
            paired += 1
            if len(samples) < 20:
                samples.append(
                    {
                        "symbol": symbol,
                        "kind": kind,
                        "eps": current.eps_basic,
                        "eps_delta_pct": cmp.eps_delta_pct,
                        "match_quality": cmp.match_quality,
                        "period_end": str(current.fiscal_period_end),
                    }
                )

    rate = (100.0 * paired / pairable) if pairable else 0.0
    summary = {
        "pdfs_scanned": n,
        "symbol_kind_groups": len(by_sym_kind),
        "pairable_groups": pairable,
        "paired_ok": paired,
        "pair_rate_pct": round(rate, 2),
        "qualities": dict(qualities),
        "samples": samples,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_json = OUT / f"cse_filing_yoy_pairing_{ts}.json"
    out_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    md = OUT / "CSE_FILING_YOY_PAIRING.md"
    md.write_text(
        "\n".join(
            [
                "# CSE filing YoY pairing harness",
                "",
                f"Generated: `{datetime.now(UTC).isoformat()}`",
                "",
                f"- PDFs scanned: **{n}**",
                f"- Pairable symbol×kind groups (≥2 extract_ok): **{pairable}**",
                f"- Successfully paired: **{paired}** ({rate:.1f}%)",
                f"- Qualities: `{dict(qualities)}`",
                "",
                f"Raw: `{out_json.name}`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2))
    print(f"Wrote {out_json}")
    if pairable and rate < 95.0:
        print("PAIR RATE BELOW 95% — investigate samples")
        raise SystemExit(2)


if __name__ == "__main__":
    main()
