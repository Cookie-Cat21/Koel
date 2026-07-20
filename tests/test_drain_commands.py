"""Track C: PDF / briefs / metrics drain helpers + CLI wiring."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from koel import __main__ as main_mod
from koel.briefs import BriefSettings
from koel.domain import Disclosure
from koel.drain import DrainResult, drain_briefs, drain_metrics, drain_pdfs
from koel.metrics import MetricsSettings


def _disc(**kwargs: Any) -> Disclosure:
    base = dict(
        id=1,
        external_id="ext-1",
        symbol="COMB.N0000",
        title="Interim Financial Statements",
        category="Financial",
        url="https://www.cse.lk/pages/announcements",
        company_name="Commercial Bank",
        published_at=datetime(2026, 1, 1, tzinfo=UTC),
        seen_at=datetime(2026, 1, 1, tzinfo=UTC),
        pdf_url=None,
    )
    base.update(kwargs)
    return Disclosure(**base)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_drain_pdfs_sets_url_from_legacy_map() -> None:
    storage = AsyncMock()
    storage.list_disclosures_missing_pdf = AsyncMock(
        return_value=[_disc(id=9, external_id="42")]
    )
    storage.set_disclosure_pdf_url = AsyncMock(return_value=True)
    cse = AsyncMock()
    cse.fetch_legacy_announcements = AsyncMock(return_value=[MagicMock()])
    settings = MagicMock(pdf_enrich_sleep_seconds=0)

    with patch(
        "koel.drain.legacy_pdf_urls_by_id",
        return_value={"42": "https://cdn.cse.lk/cmt/upload_pdf_file/x.pdf"},
    ):
        result = await drain_pdfs(
            storage=storage, cse=cse, settings=settings, limit=5
        )

    assert result == DrainResult("drain-pdfs", 1, 1, 0, 0)
    storage.set_disclosure_pdf_url.assert_awaited_once()


@pytest.mark.asyncio
async def test_drain_briefs_noop_when_disabled() -> None:
    storage = AsyncMock()
    result = await drain_briefs(
        storage=storage,
        settings=BriefSettings(enabled=False, api_key=""),
        limit=3,
    )
    assert result.updated == 0
    storage.claim_pending_briefs.assert_not_called()


@pytest.mark.asyncio
async def test_drain_briefs_calls_worker_when_enabled() -> None:
    storage = AsyncMock()
    with patch(
        "koel.drain.claim_pending_briefs", new=AsyncMock(return_value=2)
    ) as claim:
        result = await drain_briefs(
            storage=storage,
            settings=BriefSettings(enabled=True, api_key="k"),
            limit=4,
        )
    assert result.updated == 2
    claim.assert_awaited_once()


@pytest.mark.asyncio
async def test_drain_metrics_skips_non_financial() -> None:
    storage = AsyncMock()
    storage.list_disclosures_pending_metrics = AsyncMock(
        return_value=[_disc(title="Board Meeting Notice", category="Corporate")]
    )
    result = await drain_metrics(
        storage=storage,
        settings=MetricsSettings(
            financial_metrics_enabled=True,
            filing_compare_enabled=False,
            eps_calc_alerts_enabled=False,
            yoy_compare_alerts_enabled=False,
            metrics_shadow_mode=True,
            yoy_append_to_disclosure=False,
        ),
        limit=5,
    )
    assert result.skipped == 1
    assert result.updated == 0


@pytest.mark.asyncio
async def test_drain_metrics_noop_when_disabled() -> None:
    storage = AsyncMock()
    result = await drain_metrics(
        storage=storage,
        settings=MetricsSettings(
            financial_metrics_enabled=False,
            filing_compare_enabled=False,
            eps_calc_alerts_enabled=False,
            yoy_compare_alerts_enabled=False,
            metrics_shadow_mode=True,
            yoy_append_to_disclosure=False,
        ),
    )
    assert result.examined == 0
    storage.list_disclosures_pending_metrics.assert_not_called()


@pytest.mark.parametrize(
    "cmd",
    ["bot", "poller", "both", "migrate", "drain-pdfs", "drain-briefs", "drain-metrics"],
)
def test_main_force_flag_rejected_for_non_tick_including_drains(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    cmd: str,
) -> None:
    monkeypatch.setattr(main_mod, "configure_logging", lambda *a, **k: None)
    monkeypatch.setattr(
        main_mod.Settings,
        "from_env",
        lambda **_: pytest.fail("--force must reject before Settings load"),
    )
    with pytest.raises(SystemExit) as excinfo:
        main_mod.main([cmd, "--force"])
    assert excinfo.value.code == 2
    assert "--force is only valid for tick" in capsys.readouterr().err


def test_main_drain_briefs_dispatch(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(main_mod, "configure_logging", lambda *a, **k: None)
    settings = MagicMock(database_url="postgresql://koel:koel@localhost/koel")
    monkeypatch.setattr(main_mod.Settings, "from_env", lambda **_: settings)

    storage = AsyncMock()
    storage.open = AsyncMock()
    storage.close = AsyncMock()
    monkeypatch.setattr(main_mod, "Storage", lambda *_a, **_k: storage)

    async def _fake_drain(**_kwargs: Any) -> DrainResult:
        return DrainResult("drain-briefs", 2, 2, 0, 0)

    monkeypatch.setattr(main_mod, "drain_briefs", _fake_drain)
    main_mod.main(["drain-briefs", "--limit", "5"])
    out = capsys.readouterr().out
    assert "drain-briefs: examined=2 updated=2" in out


def test_main_drain_metrics_dispatch(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(main_mod, "configure_logging", lambda *a, **k: None)
    settings = MagicMock(database_url="postgresql://koel:koel@localhost/koel")
    monkeypatch.setattr(main_mod.Settings, "from_env", lambda **_: settings)
    storage = AsyncMock()
    storage.open = AsyncMock()
    storage.close = AsyncMock()
    monkeypatch.setattr(main_mod, "Storage", lambda *_a, **_k: storage)

    async def _fake(**_kwargs: Any) -> DrainResult:
        return DrainResult("drain-metrics", 4, 1, 3, 0)

    monkeypatch.setattr(main_mod, "drain_metrics", _fake)
    main_mod.main(["drain-metrics", "--limit", "4", "--all-symbols"])
    assert "drain-metrics: examined=4 updated=1" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_drain_pdfs_empty_queue() -> None:
    storage = AsyncMock()
    storage.list_disclosures_missing_pdf = AsyncMock(return_value=[])
    cse = AsyncMock()
    settings = MagicMock(pdf_enrich_sleep_seconds=0)
    result = await drain_pdfs(storage=storage, cse=cse, settings=settings)
    assert result.examined == 0
    cse.fetch_legacy_announcements.assert_not_called()


@pytest.mark.asyncio
async def test_drain_pdfs_skips_when_legacy_map_empty() -> None:
    storage = AsyncMock()
    storage.list_disclosures_missing_pdf = AsyncMock(
        return_value=[_disc(id=2, external_id="99")]
    )
    cse = AsyncMock()
    cse.fetch_legacy_announcements = AsyncMock(return_value=[])
    settings = MagicMock(pdf_enrich_sleep_seconds=0)
    with patch("koel.drain.legacy_pdf_urls_by_id", return_value={}):
        result = await drain_pdfs(storage=storage, cse=cse, settings=settings)
    assert result.skipped == 1
    assert result.updated == 0


def test_migration_014_drain_indexes_present() -> None:
    from pathlib import Path

    sql = (
        Path(__file__).resolve().parents[1]
        / "db"
        / "migrations"
        / "014_drain_indexes.sql"
    ).read_text(encoding="utf-8")
    assert "idx_disclosures_missing_pdf" in sql
    assert "idx_disclosures_has_pdf" in sql
    assert "WHERE pdf_url IS NULL" in sql
    assert "WHERE pdf_url IS NOT NULL" in sql
    # Partial indexes cannot use subquery predicates.
    assert "WHERE NOT EXISTS" not in sql
