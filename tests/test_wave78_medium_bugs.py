"""Wave78: missing isinstance regression pins for recent fail-closed guards.

Restores / completes source pins that recent waves left unlocked:

1. Storage ``claim_brief_followups`` / ``get_ready_filing_brief`` must
   isinstance-guard ``external_id`` / ``symbol`` / ``brief`` / ``message_text``
   (pins dropped when wave67 was rewritten to provider/bulk/PDF).
2. ``get_latest_ready_brief`` must isinstance-guard PG ``brief`` / ``title`` /
   ``url`` / ``external_id`` (wave75 only locked ``raw_sym`` in-source).
3. ``_row_to_rule`` must isinstance-guard ``raw_sym`` / ``raw_cat``; ``_row_to_snapshot``
   must isinstance-guard ``ts`` (wave75 locked type/symbol only).
4. CSE ``sector_row_to_snapshot`` / ``symbol_info_to_snapshot`` must
   isinstance-guard ``row.name`` / ``info.symbol`` (behavioral covered; source
   pin missing).
5. ``BriefSettings.from_env`` must isinstance-guard ``model_raw`` (wave66 pinned
   provider/enabled/api_key only).
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_storage_brief_claim_lookup_isinstance_pins() -> None:
    src = (ROOT / "chime" / "storage.py").read_text(encoding="utf-8")
    claim = src.split("async def claim_brief_followups")[1].split(
        "async def mark_brief_ready"
    )[0]
    assert "isinstance(external_id, str)" in claim
    assert "isinstance(symbol, str)" in claim
    assert "isinstance(brief, str)" in claim
    assert "isinstance(message_text, str)" in claim
    assert '(external_id or "").strip()' not in claim

    ready = src.split("async def get_ready_filing_brief")[1].split(
        "async def get_latest_ready_brief"
    )[0]
    assert "isinstance(external_id, str)" in ready
    assert "isinstance(symbol, str)" in ready
    assert "isinstance(brief, str)" in ready


def test_get_latest_ready_brief_field_isinstance_pins() -> None:
    src = (ROOT / "chime" / "storage.py").read_text(encoding="utf-8")
    chunk = src.split("async def get_latest_ready_brief")[1].split(
        "async def insert_disclosure_if_new"
    )[0]
    assert "isinstance(brief, str)" in chunk
    assert "isinstance(raw_sym, str)" in chunk
    assert "isinstance(raw_title, str)" in chunk
    assert "isinstance(raw_url, str)" in chunk
    assert "isinstance(raw_ext, str)" in chunk
    assert 'str(data.get("symbol")' not in chunk
    assert 'str(data.get("title")' not in chunk
    assert 'str(data.get("url")' not in chunk
    assert 'str(data.get("external_id")' not in chunk


def test_row_to_rule_and_snapshot_isinstance_pins() -> None:
    src = (ROOT / "chime" / "storage.py").read_text(encoding="utf-8")
    rule = src.split("def _row_to_rule")[1]
    assert "isinstance(raw_type, str)" in rule
    assert "isinstance(raw_sym, str)" in rule
    assert "isinstance(raw_cat, str)" in rule
    assert "AlertType(str(row" not in rule

    snap = src.split("def _row_to_snapshot")[1].split("def _row_to_rule")[0]
    assert "isinstance(raw_sym, str)" in snap
    assert "isinstance(ts, datetime)" in snap


def test_cse_sector_and_symbol_info_isinstance_pins() -> None:
    src = (ROOT / "chime" / "adapters" / "cse.py").read_text(encoding="utf-8")
    sector = src.split("def sector_row_to_snapshot")[1].split(
        "def symbol_info_to_snapshot"
    )[0]
    assert "isinstance(row.symbol, str)" in sector
    assert "isinstance(row.name, str)" in sector

    info = src.split("def symbol_info_to_snapshot")[1].split(
        "def announcement_to_disclosure"
    )[0]
    assert "isinstance(info.symbol, str)" in info


def test_brief_settings_model_raw_isinstance_pin() -> None:
    src = (ROOT / "chime" / "briefs" / "__init__.py").read_text(encoding="utf-8")
    chunk = src.split("def from_env")[1].split("def briefs_enabled")[0]
    assert "isinstance(model_raw, str)" in chunk
    assert "isinstance(provider_raw, str)" in chunk
    assert "isinstance(enabled_raw, str)" in chunk
    assert "isinstance(api_key_raw, str)" in chunk
