"""Wave56: medium+ bugs — fail-closed brief/PDF max caps + brief typeof.

1. ``sanitize_brief_body`` must fail-closed on non-integer / non-finite /
   ``None`` ``max_len`` via ``resolve_positive_int_cap`` — ``max(1, int(x))``
   used to raise mid Telegram alert format (missed push).
2. ``build_brief_prompt`` / provider sanitize must use the same fail-closed cap.
3. ``fetch_cdn_pdf`` must fail-closed ``max_bytes`` (``0`` still clamps to 1).
4. Dash ``sanitizeBriefText`` must typeof-guard ``briefStatus`` / ``brief``.
"""

from __future__ import annotations

from pathlib import Path

from koel.briefs import build_brief_prompt
from koel.domain import (
    BRIEF_BODY_MAX,
    resolve_positive_int_cap,
    sanitize_brief_body,
    truncate_disclosure_title,
)

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
ELL = "\u2026"


def test_resolve_positive_int_cap_fail_closed() -> None:
    assert resolve_positive_int_cap(10) == 10
    assert resolve_positive_int_cap(0) == 1
    assert resolve_positive_int_cap(-5) == 1
    assert resolve_positive_int_cap(None) == 1
    assert resolve_positive_int_cap(float("nan")) == 1
    assert resolve_positive_int_cap(float("inf")) == 1
    assert resolve_positive_int_cap("nope") == 1
    assert resolve_positive_int_cap(10_000, absolute_max=100) == 100
    # bool is an int subclass — must fail closed (w60 mypy narrow branch).
    assert resolve_positive_int_cap(True) == 1
    assert resolve_positive_int_cap(False) == 1
    assert resolve_positive_int_cap(b"12") == 12
    assert resolve_positive_int_cap(3.9) == 3


def test_sanitize_brief_body_max_len_fail_closed() -> None:
    assert sanitize_brief_body("ok", max_len=float("nan")) == ELL
    assert sanitize_brief_body("ok", max_len=None) == ELL  # type: ignore[arg-type]
    assert sanitize_brief_body("hello", max_len=3) == "he" + ELL
    assert sanitize_brief_body(123) is None  # type: ignore[arg-type]
    src = (ROOT / "koel" / "domain.py").read_text(encoding="utf-8")
    assert "resolve_positive_int_cap" in src
    assert "cap = max(1, int(max_len))" not in src
    huge = "Z" * (BRIEF_BODY_MAX + 10)
    assert sanitize_brief_body(huge, max_len=float("inf")) == ELL
    over = "Q" * 10_000
    capped = sanitize_brief_body(over, max_len=10**18)
    assert capped is not None
    assert len(capped) <= 4096
    assert capped.endswith(ELL)


def test_truncate_title_and_prompt_fail_closed() -> None:
    assert truncate_disclosure_title(None) == ""  # type: ignore[arg-type]
    assert truncate_disclosure_title("Title", max_len=float("nan")) == "Title"
    prompt = build_brief_prompt(
        symbol="JKH.N0000",
        title="AGM",
        extracted_text="BODY" * 50,
        max_chars=float("nan"),  # type: ignore[arg-type]
    )
    assert "<<<END_FILING>>>" in prompt
    assert ("<<<FILING>>>" + chr(10) + "B" + chr(10) + "<<<END_FILING>>>") in prompt


def test_fetch_cdn_pdf_and_provider_use_resolve_cap() -> None:
    extract = (ROOT / "koel" / "briefs" / "extract.py").read_text(
        encoding="utf-8"
    )
    assert "resolve_positive_int_cap" in extract
    assert "cap = max(1, int(max_bytes))" not in extract
    provider = (ROOT / "koel" / "briefs" / "provider.py").read_text(
        encoding="utf-8"
    )
    assert "resolve_positive_int_cap" in provider
    assert "max(1, int(self._settings.max_input_chars))" not in provider
    init = (ROOT / "koel" / "briefs" / "__init__.py").read_text(encoding="utf-8")
    assert "resolve_positive_int_cap" in init
    assert "cap = max(1, int(max_chars))" not in init


def test_sanitize_brief_text_typeof_guards() -> None:
    source = (WEB / "src" / "lib" / "api" / "disclosure-safe.ts").read_text(
        encoding="utf-8"
    )
    chunk = source.split("export function sanitizeBriefText")[1].split(
        "export function normalizeBriefStatus"
    )[0]
    assert 'typeof briefStatus !== "string"' in chunk
    assert 'briefStatus !== "ready"' in chunk
