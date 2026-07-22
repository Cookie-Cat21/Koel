"""Mock-pool unit tests for issuer_profiles storage helpers."""

from __future__ import annotations

import json

import pytest

from tests.test_storage_unit import _Conn, _store


@pytest.mark.asyncio
async def test_list_symbols_missing_issuer_profile() -> None:
    conn = _Conn([[{"symbol": "COMB.N0000"}, {"symbol": "HNB.N0000"}]])
    store = _store(conn)
    out = await store.list_symbols_missing_issuer_profile()
    assert out == ["COMB.N0000", "HNB.N0000"]


@pytest.mark.asyncio
async def test_list_symbols_missing_issuer_profile_skips_non_str() -> None:
    conn = _Conn([[{"symbol": 123}, {"symbol": "  jkh.n0000  "}]])
    store = _store(conn)
    out = await store.list_symbols_missing_issuer_profile()
    assert out == ["JKH.N0000"]


@pytest.mark.asyncio
async def test_upsert_issuer_profile_inserts_row() -> None:
    conn = _Conn([None])
    store = _store(conn)
    await store.upsert_issuer_profile(
        {
            "symbol": "COMB.N0000",
            "isin": "LK0053N00005",
            "board_type": "Main Board",
            "beta_aspi": 1.52,
            "beta_sl20": 1.35,
            "beta_period": "2025",
            "market_cap_pct": 4.07,
            "shares_issued": 1_000_000,
            "par_value": 1.0,
            "top_posts": [{"name": "A B", "role": "Chair"}],
            "website": "www.combank.lk",
            "auditors": "Messrs KPMG",
        }
    )
    assert any("INSERT INTO issuer_profiles" in s for s in conn.sql)
    params = conn.params[0]
    assert params[0] == "COMB.N0000"
    assert params[1] == "LK0053N00005"
    assert params[2] == "Main Board"
    assert json.loads(params[-1]) == [{"name": "A B", "role": "Chair"}]


@pytest.mark.asyncio
async def test_upsert_issuer_profile_rejects_bad_symbol() -> None:
    conn = _Conn([None])
    store = _store(conn)
    await store.upsert_issuer_profile({"symbol": ""})
    await store.upsert_issuer_profile({"symbol": 123})
    assert conn.sql == []


@pytest.mark.asyncio
async def test_upsert_issuer_profile_top_posts_string_passthrough() -> None:
    conn = _Conn([None])
    store = _store(conn)
    await store.upsert_issuer_profile(
        {"symbol": "HNB.N0000", "top_posts": '[{"name":"X","role":"Y"}]'}
    )
    assert conn.params[0][-1] == '[{"name":"X","role":"Y"}]'
