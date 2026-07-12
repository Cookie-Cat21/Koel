"""Wave8 adversarial: PDF grace vs promote, follow-up sweep, Groq model default."""

from __future__ import annotations

import pytest

from chime.briefs import BriefSettings
from tests.test_storage_unit import _Conn, _store


def test_brief_settings_groq_soft_defaults_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AI_PROVIDER=groq without AI_MODEL must not keep gemini-* (daily-cap burn)."""
    monkeypatch.setenv("AI_BRIEFS_ENABLED", "0")
    monkeypatch.setenv("AI_PROVIDER", "groq")
    monkeypatch.delenv("AI_MODEL", raising=False)
    cfg = BriefSettings.from_env()
    assert cfg.provider == "groq"
    assert cfg.model == "llama-3.3-70b-versatile"


def test_brief_settings_groq_respects_explicit_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AI_PROVIDER", "groq")
    monkeypatch.setenv("AI_MODEL", "llama-3.1-8b-instant")
    cfg = BriefSettings.from_env()
    assert cfg.model == "llama-3.1-8b-instant"


def test_brief_settings_gemini_keeps_default_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    monkeypatch.delenv("AI_MODEL", raising=False)
    cfg = BriefSettings.from_env()
    assert cfg.model == "gemini-2.0-flash"


@pytest.mark.asyncio
async def test_claim_pending_briefs_pdf_grace_sql_uses_updated_at() -> None:
    """Promote sets updated_at=now(); grace must key off that, not created_at."""
    conn = _Conn(
        [
            None,
            {"n": 0},
            [],
        ]
    )
    store = _store(conn)
    await store.claim_pending_briefs(limit=1, max_briefs_per_day=10, pdf_grace_seconds=90)
    claim_sql = next(s for s in conn.sql if "FOR UPDATE OF b SKIP LOCKED" in s)
    assert "b.updated_at" in claim_sql
    assert "NULLIF(btrim(d.pdf_url), '') IS NOT NULL" in claim_sql
    # Must not use created_at for the grace age predicate.
    assert "b.created_at\n                                < now()" not in claim_sql
    assert conn.params[-1] == (15, 90, 1)


@pytest.mark.asyncio
async def test_list_ready_briefs_excludes_already_followed_up() -> None:
    """Sweep SQL must require a delivered primary without brief_followup row."""
    conn = _Conn([[]])
    store = _store(conn)
    await store.list_ready_briefs_for_followup_sweep(limit=5, max_age_days=3)
    sql = conn.sql[0]
    assert "message_sent OR al.delivery_attempted_ok" in sql
    assert "brief_followup:" in sql
    assert "NOT EXISTS" in sql
    assert "ORDER BY b.updated_at ASC" in sql
    assert conn.params[0] == (3, 5)


def test_brief_settings_openrouter_soft_defaults_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AI_PROVIDER", "openrouter")
    monkeypatch.delenv("AI_MODEL", raising=False)
    cfg = BriefSettings.from_env()
    assert cfg.model == "openai/gpt-4o-mini"
