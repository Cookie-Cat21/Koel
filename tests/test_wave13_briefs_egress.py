"""Wave13 adversarial: briefs/PDF/Telegram egress hardening.

Medium+ findings fixed here:
1. Unbounded allowlisted filing/CDN URLs (huge path/fragment) blew past
   Telegram's 4096 limit → push fails.
2. C0/C1 controls in URL fragments leaked into Telegram bodies (and could
   glue hostile suffixes after a null).
3. Disclosure titles with controls were echoed unsanitized into alerts.
"""

from __future__ import annotations

import pytest

from koel.adapters.cse import (
    CDN_BASE,
    FILING_URL_MAX,
    allowed_cdn_pdf_url,
    allowed_filing_url,
)
from koel.bot import format_brief_lookup_reply
from koel.domain import (
    TELEGRAM_SAFE_MAX,
    AlertEvent,
    AlertType,
    disclaimer,
    format_alert_message,
    format_brief_followup,
    truncate_disclosure_title,
)


def _disclosure_event(**kwargs: object) -> AlertEvent:
    base: dict[str, object] = dict(
        rule_id=1,
        user_id=1,
        telegram_id=1,
        symbol="JKH.N0000",
        type=AlertType.DISCLOSURE,
        trigger="new disclosure",
        event_key="disclosure:w13:1",
    )
    base.update(kwargs)
    return AlertEvent(**base)  # type: ignore[arg-type]


def _assert_telegram_safe(msg: str) -> None:
    assert isinstance(msg, str)
    assert len(msg) < TELEGRAM_SAFE_MAX
    assert disclaimer() in msg
    assert "\x00" not in msg
    for ch in msg:
        if ch in ("\n", "\t"):
            continue
        assert ord(ch) >= 0x20, f"control leaked: {ch!r}"


def test_allowed_filing_url_rejects_overlong_fragment() -> None:
    huge = "https://www.cse.lk/announcements#" + ("9" * (FILING_URL_MAX + 20))
    assert allowed_filing_url(huge) is None
    assert (
        allowed_filing_url("https://www.cse.lk/announcements#99")
        == "https://www.cse.lk/announcements#99"
    )


def test_allowed_cdn_pdf_url_rejects_overlong_path() -> None:
    huge = f"{CDN_BASE}/uploadAnnounceFiles/" + ("a" * (FILING_URL_MAX + 50)) + ".pdf"
    assert allowed_cdn_pdf_url(huge) is None
    ok = f"{CDN_BASE}/uploadAnnounceFiles/short.pdf"
    assert allowed_cdn_pdf_url(ok) == ok


def test_allowed_filing_url_rejects_control_chars() -> None:
    assert allowed_filing_url("https://www.cse.lk/announcements#foo\x00bar") is None
    assert allowed_filing_url("https://www.cse.lk/announcements#foo\x07bar") is None
    assert allowed_cdn_pdf_url("https://cdn.cse.lk/x\x00.pdf") is None
    assert allowed_cdn_pdf_url("https://cdn.cse.lk/x\n.pdf") is None


def test_format_alert_message_drops_overlong_url_stays_under_cap() -> None:
    url = "https://www.cse.lk/announcements#" + ("9" * 10_000)
    msg = format_alert_message(
        _disclosure_event(
            disclosure_title="T" * 200,
            disclosure_url=url,
            filing_brief="F" * 8_000,
        )
    )
    _assert_telegram_safe(msg)
    assert "99999" not in msg


def test_format_brief_followup_drops_overlong_cdn_url() -> None:
    url = f"{CDN_BASE}/uploadAnnounceFiles/" + ("a" * 8_000) + ".pdf"
    msg = format_brief_followup(
        symbol="JKH.N0000",
        brief="B" * 9_000,
        title="AGM",
        url=url,
    )
    _assert_telegram_safe(msg)
    assert "aaaaa" not in msg


def test_format_alert_message_strips_url_controls_no_leak() -> None:
    url = "https://www.cse.lk/announcements#foo\x00barhttps://evil.example"
    msg = format_alert_message(_disclosure_event(disclosure_url=url, filing_brief="ok"))
    _assert_telegram_safe(msg)
    assert "evil.example" not in msg
    assert "\x00" not in msg


def test_truncate_disclosure_title_strips_controls() -> None:
    assert truncate_disclosure_title("AGM\x00Inject") == "AGMInject"
    assert truncate_disclosure_title("\x00\x01") == ""
    msg = format_alert_message(
        _disclosure_event(disclosure_title="Board\x00 met\nExtra", filing_brief="ok")
    )
    _assert_telegram_safe(msg)
    assert "Board metExtra" in msg or "Board met" in msg


def test_format_helpers_max_brief_plus_max_allowlisted_url() -> None:
    """Even a max-length allowlisted URL + max brief stays under 4096."""
    # Build an allowlisted URL at the FILING_URL_MAX boundary.
    base = "https://www.cse.lk/announcements#"
    frag = "x" * (FILING_URL_MAX - len(base))
    url = base + frag
    assert allowed_filing_url(url) == url
    assert len(url) == FILING_URL_MAX

    alert = format_alert_message(
        _disclosure_event(
            disclosure_title="T" * 200,
            disclosure_url=url,
            filing_brief="Z" * 8_000,
        )
    )
    follow = format_brief_followup(
        symbol="COMB.N0000",
        brief="Z" * 8_000,
        title="T" * 200,
        url=url,
    )
    lookup = format_brief_lookup_reply(
        symbol="JKH.N0000",
        brief="Z" * 8_000,
        title="T" * 200,
        url=url,
    )
    _assert_telegram_safe(alert)
    _assert_telegram_safe(follow)
    _assert_telegram_safe(lookup)


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "https://evil.example/phish",
        "https://www.cse.lk.evil.example/x",
        "https://cdn.cse.lk.evil.example/x.pdf",
        "https://user:pass@www.cse.lk/announcements",
        "http://www.cse.lk/announcements",
    ],
)
def test_hostile_urls_never_egress(url: str) -> None:
    msg = format_alert_message(_disclosure_event(disclosure_url=url, filing_brief="brief"))
    follow = format_brief_followup(symbol="JKH.N0000", brief="brief", url=url)
    _assert_telegram_safe(msg)
    _assert_telegram_safe(follow)
    assert "evil.example" not in msg
    assert "javascript:" not in msg
    assert "evil.example" not in follow
    assert "javascript:" not in follow
