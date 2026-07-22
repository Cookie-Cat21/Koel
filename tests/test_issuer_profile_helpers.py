"""Unit helpers for issuer profile normalize (no CSE / no DB)."""

from __future__ import annotations

from koel.issuer_profile_backfill import _top_posts_json, _trim_detail


def test_trim_detail_empty() -> None:
    assert _trim_detail([]) is None


def test_trim_detail_caps_and_ellipsis() -> None:
    issues = [f"sym{i}: err" for i in range(20)]
    text = _trim_detail(issues)
    assert text is not None
    assert "sym0: err" in text
    assert "…" in text or "..." in text


def test_top_posts_json_parses_and_caps() -> None:
    raw = [
        {
            "firstName": "S.",
            "lastName": "Manatunge",
            "designationOther": "Managing Director / Chief Executive Officer",
        },
        {"firstName": "", "lastName": "", "designationOther": "x"},
        {"firstName": "A", "lastName": "B", "designationOther": "Chair"},
    ]
    out = _top_posts_json(raw)
    assert len(out) == 2
    assert out[0]["name"] == "S. Manatunge"
    assert "Managing Director" in out[0]["role"]


def test_top_posts_json_rejects_non_list() -> None:
    assert _top_posts_json(None) == []
    assert _top_posts_json("x") == []
