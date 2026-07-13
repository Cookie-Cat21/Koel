"""Wave91: CSE adapter must reject boolean numeric payloads.

Pydantic's default coercion turns ``True`` into ``1`` / ``1.0``. For CSE market
data that can persist fake prices, sector ids, or disclosure ids instead of
failing closed on poisoned JSON.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel, ValidationError

from chime.adapters.cse import (
    AnnouncementRow,
    CSEClient,
    LegacyAnnouncementRow,
    SectorRow,
    SymbolInfo,
    TradeSummaryRow,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.asyncio
async def test_trade_summary_skips_bool_price_not_fake_one_lkr_snapshot() -> None:
    client = CSEClient(client=AsyncMock())
    client._request = AsyncMock(  # type: ignore[method-assign]
        return_value={
            "reqTradeSummery": [
                {"symbol": "BOOL.N0000", "price": True},
                {"symbol": "JKH.N0000", "price": 185.5},
            ]
        }
    )

    out = await client.fetch_trade_summary()

    assert [(snap.symbol, snap.price) for snap in out] == [("JKH.N0000", 185.5)]
    assert all(snap.symbol != "BOOL.N0000" for snap in out)


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (TradeSummaryRow, {"symbol": "BOOL.N0000", "price": True}),
        (SymbolInfo, {"symbol": "BOOL.N0000", "lastTradedPrice": True}),
        (SectorRow, {"sectorId": True, "symbol": "IDX", "name": "Index"}),
        (AnnouncementRow, {"announcementId": True}),
        (LegacyAnnouncementRow, {"announcementId": True}),
    ],
)
def test_cse_row_models_reject_bool_numeric_coercion(
    model: type[BaseModel],
    payload: dict[str, Any],
) -> None:
    with pytest.raises(ValidationError, match="boolean is not a valid CSE numeric value"):
        model.model_validate(payload)


def test_cse_numeric_bool_source_pin() -> None:
    src = (ROOT / "chime" / "adapters" / "cse.py").read_text(encoding="utf-8")
    assert "field_validator" in src
    assert "isinstance(value, bool)" in src
    assert "boolean is not a valid CSE numeric value" in src
