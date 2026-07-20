"""Wave61: medium+ bugs — body abs-cap, formatTs range, session/category.

1. ``readBoundedResponseText`` / ``readJsonBody`` must abs-cap ``maxBytes`` via
   ``resolveBoundedBodyCap`` / ``MAX_BOUNDED_BODY_BYTES`` — integer
   ``Number.MAX_SAFE_INTEGER`` used to let a misbuilt caller stream-allocate
   past any product 1 MiB bound (parity ``resolveSanitizeTextCap``).
2. ``formatTs`` must fail-closed on out-of-range Date values via
   ``MAX_DATE_MS`` (parity ``safeToIsoString``) — length-gated ISO still
   admitted extreme timestamps that ballooned / threw in ``toLocaleString``.
3. ``verifySessionToken`` must typeof-guard ``token`` / ``secret`` — non-strings
   used to throw on ``.split`` / HMAC update instead of a clean auth reject.
4. ``sanitizeDisclosureCategory`` / ``mapRule`` must not ``String()``-coerce
   non-string categories; Python ``_row_to_rule`` must not ``str()``-coerce
   (objects used to bypass the isinstance fail-closed path).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from koel.domain import AlertType
from koel.storage import _row_to_rule

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_bounded_body_cap_abs_ceiling() -> None:
    bounded = (WEB / "src" / "lib" / "api" / "read-bounded-text.ts").read_text(
        encoding="utf-8"
    )
    assert "MAX_BOUNDED_BODY_BYTES" in bounded
    assert "1_048_576" in bounded
    assert "export function resolveBoundedBodyCap" in bounded
    chunk = bounded.split("export function resolveBoundedBodyCap")[1].split(
        "export async function readBoundedResponseText"
    )[0]
    assert "Number.isSafeInteger(maxBytes)" in chunk
    assert "maxBytes > MAX_BOUNDED_BODY_BYTES" in chunk
    assert "resolveBoundedBodyCap(maxBytes)" in bounded

    json_body = (WEB / "src" / "lib" / "api" / "read-json-body.ts").read_text(
        encoding="utf-8"
    )
    assert "resolveBoundedBodyCap" in json_body
    assert "resolveBoundedBodyCap(maxBytes)" in json_body
    assert 'typeof maxBytes === "number" &&' not in json_body


def test_format_ts_date_range_gate() -> None:
    source = (WEB / "src" / "lib" / "format.ts").read_text(encoding="utf-8")
    assert "MAX_DATE_MS" in source
    chunk = source.split("export function formatTs")[1].split(
        "export function alertTypeLabel"
    )[0]
    assert "Math.abs(t) > MAX_DATE_MS" in chunk
    assert "Number.isNaN(t)" in chunk
    assert "toLocaleString" in chunk
    assert "catch {" in chunk

    time_src = (WEB / "src" / "lib" / "api" / "time.ts").read_text(
        encoding="utf-8"
    )
    assert "export const MAX_DATE_MS" in time_src
    assert "export export" not in time_src


def test_verify_session_token_typeof_guard() -> None:
    source = (WEB / "src" / "lib" / "auth" / "session.ts").read_text(
        encoding="utf-8"
    )
    chunk = source.split("export function verifySessionToken")[1].split(
        "export function mintCsrfToken"
    )[0]
    assert "token: unknown" in chunk
    assert "secret: unknown" in chunk
    assert 'typeof token !== "string"' in chunk
    assert 'typeof secret !== "string"' in chunk


def test_category_no_string_coerce() -> None:
    safe = (WEB / "src" / "lib" / "api" / "disclosure-safe.ts").read_text(
        encoding="utf-8"
    )
    assert "export function sanitizeDisclosureCategory(" in safe
    assert "category: unknown" in safe
    cat_chunk = safe.split("export function sanitizeDisclosureCategory")[1]
    assert 'typeof category !== "string"' in cat_chunk

    db = (WEB / "src" / "lib" / "db.ts").read_text(encoding="utf-8")
    assert "sanitizeDisclosureCategory(row.category)" in db
    assert "String(row.category)" not in db


def test_row_to_rule_rejects_non_string_category() -> None:
    base = {
        "id": 1,
        "user_id": 2,
        "telegram_id": 3,
        "symbol": "JKH.N0000",
        "type": AlertType.DISCLOSURE.value,
        "threshold": None,
        "active": True,
        "armed": True,
        "created_at": datetime.now(UTC),
    }
    for bad in ({"x": 1}, 42, True, b"bytes"):
        rule = _row_to_rule({**base, "category": bad})
        assert rule.category is None
    ok = _row_to_rule({**base, "category": "Financial"})
    assert ok.category == "Financial"
