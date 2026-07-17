"""Fill pending disclosure briefs without an external LLM.

Builds short NFA-safe text from title + optional ``filing_metrics`` /
``filing_comparisons`` already in Postgres. Used when Groq/Gemini is
unavailable or rate-limited.
"""

from __future__ import annotations

from dataclasses import dataclass

from chime.domain import sanitize_brief_body
from chime.logging_setup import get_logger
from chime.storage import Storage

log = get_logger(__name__)

LOCAL_MODEL = "local-metrics-brief-v1"


@dataclass(frozen=True, slots=True)
class LocalFillResult:
    examined: int
    ready: int
    skipped: int
    errors: int


def _fmt_num(val: object) -> str | None:
    if isinstance(val, bool) or not isinstance(val, int | float):
        return None
    x = float(val)
    if x != x:  # NaN
        return None
    ax = abs(x)
    if ax >= 1_000_000_000:
        return f"{x / 1_000_000_000:.2f}B"
    if ax >= 1_000_000:
        return f"{x / 1_000_000:.2f}M"
    if ax >= 1_000:
        return f"{x / 1_000:.2f}K"
    if ax >= 10:
        return f"{x:.2f}"
    return f"{x:.4g}"


def build_local_brief(
    *,
    symbol: str,
    title: str,
    kind: str | None = None,
    period_end: object = None,
    revenue: object = None,
    profit: object = None,
    eps: object = None,
    extract_ok: bool = False,
    eps_yoy: object = None,
    rev_yoy: object = None,
    profit_yoy: object = None,
) -> str:
    lines: list[str] = []
    ttl = (title or "").strip() or "a company filing"
    lines.append(f"{symbol} published “{ttl}”.")
    if kind or period_end:
        bits = []
        if kind:
            bits.append(str(kind))
        if period_end is not None:
            bits.append(f"period ending {period_end}")
        lines.append("This is recorded as a " + " ".join(bits) + " filing.")
    if extract_ok:
        facts: list[str] = []
        e = _fmt_num(eps)
        r = _fmt_num(revenue)
        p = _fmt_num(profit)
        if e:
            facts.append(f"basic EPS {e}")
        if r:
            facts.append(f"revenue {r}")
        if p:
            facts.append(f"profit {p}")
        if facts:
            lines.append(
                "Extracted figures (verify in the official PDF): "
                + "; ".join(facts)
                + "."
            )
        yoy_bits: list[str] = []
        for label, val in (
            ("EPS", eps_yoy),
            ("revenue", rev_yoy),
            ("profit", profit_yoy),
        ):
            if isinstance(val, bool) or not isinstance(val, int | float):
                continue
            yoy_bits.append(f"{label} YoY {float(val):+.2f}%")
        if yoy_bits:
            lines.append(
                "Compared with the matched prior-year period: "
                + "; ".join(yoy_bits)
                + "."
            )
    else:
        lines.append(
            "No verified extracted metrics are attached yet; "
            "see the CSE filing PDF for official numbers."
        )
    lines.append("Not financial advice — informational only.")
    text = " ".join(lines)
    cleaned = sanitize_brief_body(text)
    if cleaned is None:
        raise ValueError("local brief empty after sanitize")
    return cleaned


async def fill_pending_briefs_local(
    *,
    storage: Storage,
    limit: int = 50,
    extract_ok_only: bool = True,
    include_skipped: bool = True,
    require_pdf: bool = False,
) -> LocalFillResult:
    """Mark pending/failed/skipped briefs ready using local metric-based text.

    First-run / AI-off boards enqueue rows as ``skipped``; include those so a
    local fill can populate the dash without Groq/Gemini. Title-only briefs
    are allowed when ``require_pdf`` is false (default for board-wide soak).
    """
    # Cap per call; callers loop for full-board drains.
    lim = max(1, min(int(limit), 2000))
    statuses = ("pending", "failed", "skipped") if include_skipped else ("pending", "failed")
    status_sql = ", ".join(f"'{s}'" for s in statuses)
    pdf_sql = "AND d.pdf_url IS NOT NULL" if require_pdf else ""
    extract_sql = "AND fm.extract_ok = TRUE" if extract_ok_only else ""
    async with storage._pool.connection() as conn:
        rows = await (
            await conn.execute(
                f"""
                SELECT
                    d.id AS disclosure_id,
                    d.symbol,
                    d.title,
                    fm.kind,
                    fm.fiscal_period_end,
                    fm.revenue,
                    fm.profit,
                    fm.eps_basic,
                    fm.extract_ok,
                    fc.eps_delta_pct,
                    fc.revenue_delta_pct,
                    fc.profit_delta_pct
                FROM disclosure_briefs b
                JOIN disclosures d ON d.id = b.disclosure_id
                LEFT JOIN filing_metrics fm ON fm.disclosure_id = d.id
                LEFT JOIN filing_comparisons fc ON fc.filing_metrics_id = fm.id
                WHERE b.status IN ({status_sql})
                  {pdf_sql}
                  {extract_sql}
                ORDER BY d.published_at DESC NULLS LAST, d.id DESC
                LIMIT %s
                """,
                (lim,),
            )
        ).fetchall()

    examined = ready = skipped = errors = 0
    for row in rows:
        examined += 1
        d = dict(row)
        did = d.get("disclosure_id")
        if not isinstance(did, int) or isinstance(did, bool):
            skipped += 1
            continue
        try:
            brief = build_local_brief(
                symbol=str(d.get("symbol") or "?"),
                title=str(d.get("title") or ""),
                kind=d.get("kind") if isinstance(d.get("kind"), str) else None,
                period_end=d.get("fiscal_period_end"),
                revenue=d.get("revenue"),
                profit=d.get("profit"),
                eps=d.get("eps_basic"),
                extract_ok=bool(d.get("extract_ok")),
                eps_yoy=d.get("eps_delta_pct"),
                rev_yoy=d.get("revenue_delta_pct"),
                profit_yoy=d.get("profit_delta_pct"),
            )
            ok = await storage.mark_brief_ready(
                did, brief=brief, model=LOCAL_MODEL
            )
            if ok:
                ready += 1
            else:
                skipped += 1
        except Exception as exc:
            log.warning(
                "local_brief_fill_failed",
                disclosure_id=did,
                error=str(exc)[:200],
            )
            errors += 1
    log.info(
        "local_brief_fill_done",
        examined=examined,
        ready=ready,
        skipped=skipped,
        errors=errors,
    )
    return LocalFillResult(examined, ready, skipped, errors)
