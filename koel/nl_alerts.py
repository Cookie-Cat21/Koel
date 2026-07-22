"""Natural-language alert parsing — LLM (optional) or deterministic patterns.

The parser never evaluates market data. It only maps free text into a
structured ``ParsedAlert``-compatible dict that the bot echoes for confirm.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

from koel.domain import MAX_ALERT_THRESHOLD, AlertType, disclaimer
from koel.logging_setup import get_logger

log = get_logger(__name__)

# Common English patterns — work without an API key.
_ABOVE_RE = re.compile(
    r"(?P<sym>[A-Za-z0-9]{1,12}(?:\.[A-Za-z0-9]{1,8})?)\s+"
    r"(?:goes\s+)?(?:above|over|crosses?\s+above|hits?)\s+"
    r"(?P<thr>[\d,]+(?:\.\d+)?)",
    re.I,
)
_BELOW_RE = re.compile(
    r"(?P<sym>[A-Za-z0-9]{1,12}(?:\.[A-Za-z0-9]{1,8})?)\s+"
    r"(?:goes\s+)?(?:below|under|crosses?\s+below|drops?\s+below|falls?\s+below)\s+"
    r"(?P<thr>[\d,]+(?:\.\d+)?)",
    re.I,
)
_MOVE_RE = re.compile(
    r"(?P<sym>[A-Za-z0-9]{1,12}(?:\.[A-Za-z0-9]{1,8})?)\s+"
    r"(?:drops?|falls?|moves?|rises?|gains?|moves?\s+by)\s+"
    r"(?P<thr>[\d,]+(?:\.\d+)?)\s*%",
    re.I,
)
_MOVE_FROM_RE = re.compile(
    r"(?P<sym>[A-Za-z0-9]{1,12}(?:\.[A-Za-z0-9]{1,8})?)\s+"
    r"(?:drops?|falls?|moves?|rises?|gains?)\s+"
    r"(?P<thr>[\d,]+(?:\.\d+)?)\s*%\s+from\s+"
    r"(?P<ref>[\d,]+(?:\.\d+)?)",
    re.I,
)
_DISCLOSURE_RE = re.compile(
    r"(?P<sym>[A-Za-z0-9]{1,12}(?:\.[A-Za-z0-9]{1,8})?)\s+"
    r"(?:has\s+a\s+|has\s+|gets?\s+a\s+|gets?\s+)?"
    r"(?:new\s+)?(?:disclosure|announcement|filing)s?\b",
    re.I,
)
_HIGH52_RE = re.compile(
    r"(?P<sym>[A-Za-z0-9]{1,12}(?:\.[A-Za-z0-9]{1,8})?)\s+"
    r"(?:hits?\s+|makes?\s+|reaches?\s+|goes?\s+to\s+)?"
    r"(?:a\s+)?(?:new\s+)?(?:52[\s-]?week|52w)\s+high\b",
    re.I,
)
_LOW52_RE = re.compile(
    r"(?P<sym>[A-Za-z0-9]{1,12}(?:\.[A-Za-z0-9]{1,8})?)\s+"
    r"(?:hits?\s+|makes?\s+|reaches?\s+|goes?\s+to\s+)?"
    r"(?:a\s+)?(?:new\s+)?(?:52[\s-]?week|52w)\s+low\b",
    re.I,
)
_SYMBOL_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "new",
        "if",
        "when",
        "me",
        "my",
        "on",
        "to",
        "for",
        "has",
        "have",
        "gets",
        "get",
        "hits",
        "hit",
        "and",
        "or",
    }
)
_MA_RE = re.compile(
    r"(?P<sym>[A-Za-z0-9]{1,12}(?:\.[A-Za-z0-9]{1,8})?)\s+"
    r"(?:cross(?:es|ing)?\s+)?(?:the\s+)?(?P<thr>20|50|200)[\s-]?day\s+(?:ma|sma|moving\s+average)\b",
    re.I,
)
_LEADING_FILLER_RE = re.compile(
    r"^(?:alert\s+me\s+(?:when|if)|tell\s+me\s+(?:when|if)|notify\s+me\s+(?:when|if)|"
    r"ping\s+me\s+(?:when|if)|when|if)\s+",
    re.I,
)


@dataclass(frozen=True)
class NLParsedAlert:
    """Structured alert intent from free text (never evaluated against prices)."""

    alert_type: AlertType
    symbol: str
    threshold: float | None = None
    category: str | None = None
    ref_price: float | None = None
    source: str = "pattern"  # pattern | llm


def nl_alerts_enabled() -> bool:
    """True when ``AI_NL_ALERTS_ENABLED=1`` (deterministic patterns always available
    to the bot when this is on; LLM used only when a key is also present).
    """
    raw = os.getenv("AI_NL_ALERTS_ENABLED", "0")
    return isinstance(raw, str) and raw.strip() == "1"


def _parse_positive(token: str) -> float | None:
    if not isinstance(token, str):
        return None
    s = token.strip().replace(",", "")
    try:
        value = float(s)
    except ValueError:
        return None
    if not (value > 0) or value > MAX_ALERT_THRESHOLD:
        return None
    return value


def _valid_symbol(raw: str) -> str | None:
    if not isinstance(raw, str):
        return None
    sym = raw.strip().upper()
    if not sym or sym.lower() in _SYMBOL_STOPWORDS:
        return None
    if len(sym) < 2 and "." not in sym:
        return None
    return sym


def parse_alert_natural_language(text: str) -> NLParsedAlert | None:
    """Deterministic NL → structured alert. Returns None if unrecognized.

    Strips leading filler ("alert me when", "tell me if", …) then matches
    common CSE alert phrasings. Fail-closed on non-str / empty.
    """
    if not isinstance(text, str):
        return None
    cleaned = " ".join(text.strip().split())
    if not cleaned or len(cleaned) > 400:
        return None
    body = _LEADING_FILLER_RE.sub("", cleaned).strip()
    if not body:
        return None

    m = _MOVE_FROM_RE.search(body)
    if m:
        sym = _valid_symbol(m.group("sym"))
        thr = _parse_positive(m.group("thr"))
        ref = _parse_positive(m.group("ref"))
        if sym and thr is not None and ref is not None:
            return NLParsedAlert(
                AlertType.REF_MOVE, sym, threshold=thr, ref_price=ref
            )

    m = _MOVE_RE.search(body)
    if m:
        sym = _valid_symbol(m.group("sym"))
        thr = _parse_positive(m.group("thr"))
        if sym and thr is not None:
            return NLParsedAlert(AlertType.DAILY_MOVE, sym, threshold=thr)

    m = _ABOVE_RE.search(body)
    if m:
        sym = _valid_symbol(m.group("sym"))
        thr = _parse_positive(m.group("thr"))
        if sym and thr is not None:
            return NLParsedAlert(AlertType.PRICE_ABOVE, sym, threshold=thr)

    m = _BELOW_RE.search(body)
    if m:
        sym = _valid_symbol(m.group("sym"))
        thr = _parse_positive(m.group("thr"))
        if sym and thr is not None:
            return NLParsedAlert(AlertType.PRICE_BELOW, sym, threshold=thr)

    m = _MA_RE.search(body)
    if m:
        sym = _valid_symbol(m.group("sym"))
        thr = _parse_positive(m.group("thr"))
        if sym and thr in (20.0, 50.0, 200.0):
            return NLParsedAlert(AlertType.MA_CROSS, sym, threshold=thr)

    m = _HIGH52_RE.search(body)
    if m:
        sym = _valid_symbol(m.group("sym"))
        if sym:
            return NLParsedAlert(AlertType.HIGH_52W, sym)

    m = _LOW52_RE.search(body)
    if m:
        sym = _valid_symbol(m.group("sym"))
        if sym:
            return NLParsedAlert(AlertType.LOW_52W, sym)

    m = _DISCLOSURE_RE.search(body)
    if m:
        sym = _valid_symbol(m.group("sym"))
        if sym:
            return NLParsedAlert(AlertType.DISCLOSURE, sym)

    return None


def describe_nl_alert(parsed: NLParsedAlert) -> str:
    """Human-readable confirm line for an NL-parsed alert."""
    sym = parsed.symbol
    if parsed.alert_type == AlertType.PRICE_ABOVE:
        return f"{sym} above {parsed.threshold:g}"
    if parsed.alert_type == AlertType.PRICE_BELOW:
        return f"{sym} below {parsed.threshold:g}"
    if parsed.alert_type == AlertType.DAILY_MOVE:
        return f"{sym} move {parsed.threshold:g}%"
    if parsed.alert_type == AlertType.REF_MOVE:
        return f"{sym} move {parsed.threshold:g}% from {parsed.ref_price:g}"
    if parsed.alert_type == AlertType.MA_CROSS:
        return f"{sym} ma {parsed.threshold:g}"
    if parsed.alert_type == AlertType.HIGH_52W:
        return f"{sym} high52"
    if parsed.alert_type == AlertType.LOW_52W:
        return f"{sym} low52"
    if parsed.alert_type == AlertType.DISCLOSURE:
        return f"{sym} disclosure"
    return f"{sym} {parsed.alert_type.value}"


def nl_confirm_text(parsed: NLParsedAlert) -> str:
    return (
        f"I read that as: /alert {describe_nl_alert(parsed)}\n"
        "Confirm to create this alert?\n"
        f"{disclaimer()}"
    )


def encode_nl_confirm_payload(parsed: NLParsedAlert) -> str:
    """Compact callback payload (Telegram callback_data ≤ 64 bytes)."""
    # Format: nlok:TYPE:SYMBOL:THR:REF  (THR/REF empty when unused)
    thr = "" if parsed.threshold is None else f"{parsed.threshold:g}"
    ref = "" if parsed.ref_price is None else f"{parsed.ref_price:g}"
    # Type short codes keep us under 64 bytes.
    type_code = {
        AlertType.PRICE_ABOVE: "a",
        AlertType.PRICE_BELOW: "b",
        AlertType.DAILY_MOVE: "m",
        AlertType.REF_MOVE: "r",
        AlertType.MA_CROSS: "c",
        AlertType.HIGH_52W: "h",
        AlertType.LOW_52W: "l",
        AlertType.DISCLOSURE: "d",
    }.get(parsed.alert_type)
    if type_code is None:
        return ""
    payload = f"nlok:{type_code}:{parsed.symbol}:{thr}:{ref}"
    if len(payload) > 64:
        return ""
    return payload


def decode_nl_confirm_payload(data: str) -> NLParsedAlert | None:
    if not isinstance(data, str) or not data.startswith("nlok:"):
        return None
    parts = data.split(":")
    if len(parts) != 5:
        return None
    _, code, symbol, thr_s, ref_s = parts
    type_map = {
        "a": AlertType.PRICE_ABOVE,
        "b": AlertType.PRICE_BELOW,
        "m": AlertType.DAILY_MOVE,
        "r": AlertType.REF_MOVE,
        "c": AlertType.MA_CROSS,
        "h": AlertType.HIGH_52W,
        "l": AlertType.LOW_52W,
        "d": AlertType.DISCLOSURE,
    }
    alert_type = type_map.get(code)
    if alert_type is None or not symbol:
        return None
    thr = _parse_positive(thr_s) if thr_s else None
    ref = _parse_positive(ref_s) if ref_s else None
    if alert_type in (
        AlertType.PRICE_ABOVE,
        AlertType.PRICE_BELOW,
        AlertType.DAILY_MOVE,
        AlertType.MA_CROSS,
    ) and thr is None:
        return None
    if alert_type == AlertType.REF_MOVE and (thr is None or ref is None):
        return None
    if alert_type == AlertType.MA_CROSS and thr not in (20.0, 50.0, 200.0):
        return None
    return NLParsedAlert(
        alert_type=alert_type,
        symbol=symbol.upper(),
        threshold=thr,
        ref_price=ref,
        source="pattern",
    )


async def parse_alert_with_optional_llm(text: str) -> NLParsedAlert | None:
    """Try deterministic patterns first; optionally escalate to Gemini JSON parse.

    LLM path requires ``AI_NL_ALERTS_ENABLED=1`` and ``AI_API_KEY``. On any
    LLM failure, returns the pattern result (or None). Never raises.
    """
    pattern = parse_alert_natural_language(text)
    if pattern is not None:
        return pattern
    if not nl_alerts_enabled():
        return None
    api_key = os.getenv("AI_API_KEY", "")
    if not isinstance(api_key, str) or not api_key.strip():
        return None
    try:
        return await _llm_parse(text, api_key=api_key.strip())
    except Exception as exc:  # noqa: BLE001 — fail closed to None
        log.warning("nl_alert_llm_failed", error=str(exc))
        return None


async def _llm_parse(text: str, *, api_key: str) -> NLParsedAlert | None:
    """Ask Gemini for a JSON alert intent; validate strictly before accepting."""
    import httpx

    model = os.getenv("AI_MODEL", "gemini-2.0-flash-lite")
    if not isinstance(model, str) or not model.strip():
        model = "gemini-2.0-flash-lite"
    prompt = (
        "Parse this CSE stock alert request into JSON only. "
        "Schema: {\"type\":\"price_above|price_below|daily_move|ref_move|"
        "ma_cross|high_52w|low_52w|disclosure\",\"symbol\":\"TICKER\","
        "\"threshold\":number|null,\"ref_price\":number|null}. "
        "Use only types listed. ma_cross threshold must be 20, 50, or 200. "
        "If unclear, return {\"type\":null}. Text:\n"
        f"{text[:400]}"
    )
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model.strip()}:generateContent?key={api_key}"
    )
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 200},
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, json=body)
        resp.raise_for_status()
        data: Any = resp.json()
    candidates = data.get("candidates") if isinstance(data, dict) else None
    if not isinstance(candidates, list) or not candidates:
        return None
    parts = (
        candidates[0].get("content", {}).get("parts")
        if isinstance(candidates[0], dict)
        else None
    )
    if not isinstance(parts, list) or not parts:
        return None
    raw = parts[0].get("text") if isinstance(parts[0], dict) else None
    if not isinstance(raw, str):
        return None
    # Extract JSON object even if model wraps in markdown fences.
    match = re.search(r"\{[^{}]+\}", raw)
    if not match:
        return None
    try:
        obj = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    type_raw = obj.get("type")
    if not isinstance(type_raw, str) or not type_raw:
        return None
    try:
        alert_type = AlertType(type_raw)
    except ValueError:
        return None
    if alert_type not in {
        AlertType.PRICE_ABOVE,
        AlertType.PRICE_BELOW,
        AlertType.DAILY_MOVE,
        AlertType.REF_MOVE,
        AlertType.MA_CROSS,
        AlertType.HIGH_52W,
        AlertType.LOW_52W,
        AlertType.DISCLOSURE,
    }:
        return None
    sym = obj.get("symbol")
    if not isinstance(sym, str) or not sym.strip():
        return None
    thr_raw = obj.get("threshold")
    ref_raw = obj.get("ref_price")
    thr = (
        float(thr_raw)
        if isinstance(thr_raw, (int, float)) and not isinstance(thr_raw, bool)
        else None
    )
    ref = (
        float(ref_raw)
        if isinstance(ref_raw, (int, float)) and not isinstance(ref_raw, bool)
        else None
    )
    if thr is not None and (thr <= 0 or thr > MAX_ALERT_THRESHOLD):
        return None
    if ref is not None and (ref <= 0 or ref > MAX_ALERT_THRESHOLD):
        return None
    if alert_type == AlertType.MA_CROSS and thr not in (20.0, 50.0, 200.0):
        return None
    if alert_type in (
        AlertType.PRICE_ABOVE,
        AlertType.PRICE_BELOW,
        AlertType.DAILY_MOVE,
        AlertType.MA_CROSS,
    ) and thr is None:
        return None
    if alert_type == AlertType.REF_MOVE and (thr is None or ref is None):
        return None
    return NLParsedAlert(
        alert_type=alert_type,
        symbol=sym.strip().upper(),
        threshold=thr,
        ref_price=ref,
        source="llm",
    )
