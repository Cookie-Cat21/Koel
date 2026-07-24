"""Feature Pack v2 sector-relative enricher tests."""

from __future__ import annotations

import json
import math
import statistics
import tempfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from koel.domain import DailyBar
from koel.ml.dataset import Sample
from koel.ml.feature_pack_v1 import FEATURE_PACK_V1_NAMES, enrich_feature_pack_v1
from koel.ml.feature_pack_v2 import (
    load_sector_map_for_v2,
    load_sector_map_from_json,
    resolve_sector_map_path,
)


def _bars(
    *,
    symbol: str = "TEST.N0000",
    prices: list[float] | None = None,
    start: date | None = None,
    count: int = 30,
) -> list[DailyBar]:
    day0 = start or date(2025, 1, 1)
    out: list[DailyBar] = []
    for index in range(count):
        day = day0 + timedelta(days=index)
        price = prices[index] if prices and index < len(prices) else 10.0 + index * 0.1
        out.append(
            DailyBar(
                symbol=symbol,
                trade_date=day,
                price=price,
                high=price * 1.01,
                low=price * 0.99,
                open=price,
                volume=1000.0 + index * 10.0,
                source_period=5,
                bar_ts=datetime(day.year, day.month, day.day, tzinfo=UTC),
            )
        )
    return out


def _sample(symbol: str, as_of: date, *, x: tuple[float, ...] = ()) -> Sample:
    return Sample(
        symbol=symbol,
        as_of=as_of,
        x=x,
        y_ret=0.01,
        y_dir=1.0,
        horizon=1,
        target_date=as_of + timedelta(days=1),
    )


def _feature_index(name: str) -> int:
    return -(len(FEATURE_PACK_V1_NAMES) - FEATURE_PACK_V1_NAMES.index(name))


def test_load_sector_map_from_json_normalizes_symbols() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "sector_map.json"
        path.write_text(
            json.dumps({"abc.n0000": "Banks", " XYZ.N0001 ": "Plantations"}),
            encoding="utf-8",
        )
        sector_map = load_sector_map_from_json(path)
    assert sector_map == {"ABC.N0000": "Banks", "XYZ.N0001": "Plantations"}


def test_sector_relative_uses_same_day_peer_median() -> None:
    """fp_rel_ret_1d subtracts sector median from peers on the same as_of."""
    prices_a = [10.0 + index * 0.5 for index in range(30)]
    prices_b = [20.0 + index * 0.2 for index in range(30)]
    prices_c = [30.0 + index * 1.0 for index in range(30)]
    bars_a = _bars(symbol="A.N0000", prices=prices_a)
    bars_b = _bars(symbol="B.N0000", prices=prices_b)
    bars_c = _bars(symbol="C.N0000", prices=prices_c)
    as_of = bars_a[24].trade_date
    sector_map = {"A.N0000": "Tech", "B.N0000": "Tech", "C.N0000": "Banks"}

    samples = [
        _sample("A.N0000", as_of),
        _sample("B.N0000", as_of),
        _sample("C.N0000", as_of),
    ]
    series = {"A.N0000": bars_a, "B.N0000": bars_b, "C.N0000": bars_c}

    enriched = enrich_feature_pack_v1(samples, series, sector_map=sector_map)
    by_symbol = {row.symbol: row for row in enriched}

    ret_a = by_symbol["A.N0000"].x[_feature_index("fp_ret_1d")]
    ret_b = by_symbol["B.N0000"].x[_feature_index("fp_ret_1d")]
    rel_a = by_symbol["A.N0000"].x[_feature_index("fp_rel_ret_1d")]
    rel_b = by_symbol["B.N0000"].x[_feature_index("fp_rel_ret_1d")]
    market_a = by_symbol["A.N0000"].x[_feature_index("fp_rel_ret_1d_market")]
    use_sector_a = by_symbol["A.N0000"].x[_feature_index("fp_use_sector")]
    use_sector_c = by_symbol["C.N0000"].x[_feature_index("fp_use_sector")]

    sector_median = statistics.median([ret_a, ret_b])
    assert rel_a == pytest.approx(ret_a - sector_median)
    assert rel_b == pytest.approx(ret_b - sector_median)
    assert rel_a != pytest.approx(market_a)
    assert use_sector_a == pytest.approx(1.0)
    assert use_sector_c == pytest.approx(1.0)


def test_sector_relative_without_map_keeps_market_fallback() -> None:
    bars_a = _bars(symbol="A.N0000")
    bars_b = _bars(symbol="B.N0000")
    as_of = bars_a[24].trade_date
    samples = [_sample("A.N0000", as_of), _sample("B.N0000", as_of)]
    series = {"A.N0000": bars_a, "B.N0000": bars_b}

    enriched = enrich_feature_pack_v1(samples, series)
    row = enriched[0]
    rel = row.x[_feature_index("fp_rel_ret_1d")]
    market = row.x[_feature_index("fp_rel_ret_1d_market")]
    assert rel == pytest.approx(market)
    assert row.x[_feature_index("fp_use_sector")] == pytest.approx(0.0)


def test_future_bars_do_not_change_sector_relative_features() -> None:
    bars_a = _bars(symbol="A.N0000")
    bars_b = _bars(symbol="B.N0000")
    as_of = bars_a[19].trade_date
    sector_map = {"A.N0000": "Tech", "B.N0000": "Tech"}
    samples = [_sample("A.N0000", as_of), _sample("B.N0000", as_of)]
    series = {"A.N0000": bars_a, "B.N0000": bars_b}

    before = enrich_feature_pack_v1(samples, series, sector_map=sector_map)
    before_rel = before[0].x[_feature_index("fp_rel_ret_1d")]
    before_use = before[0].x[_feature_index("fp_use_sector")]

    poisoned_a = list(bars_a)
    poisoned_a[-1] = poisoned_a[-1].model_copy(update={"price": 999.0})
    poisoned_b = list(bars_b)
    poisoned_b[-1] = poisoned_b[-1].model_copy(update={"price": 999.0})
    after = enrich_feature_pack_v1(
        samples,
        {"A.N0000": poisoned_a, "B.N0000": poisoned_b},
        sector_map=sector_map,
    )
    after_rel = after[0].x[_feature_index("fp_rel_ret_1d")]
    after_use = after[0].x[_feature_index("fp_use_sector")]

    assert after_rel == pytest.approx(before_rel)
    assert after_use == pytest.approx(before_use)


def test_sector_median_excludes_other_days() -> None:
    """Peers on a different as_of must not affect today's sector median."""
    bars_a = _bars(symbol="A.N0000", prices=[10.0 + index for index in range(30)])
    bars_b = _bars(symbol="B.N0000", prices=[20.0 + index * 0.1 for index in range(30)])
    sector_map = {"A.N0000": "Tech", "B.N0000": "Tech"}
    day_early = bars_a[19].trade_date
    day_late = bars_a[24].trade_date

    early = enrich_feature_pack_v1(
        [_sample("A.N0000", day_early), _sample("B.N0000", day_early)],
        {"A.N0000": bars_a, "B.N0000": bars_b},
        sector_map=sector_map,
    )
    late = enrich_feature_pack_v1(
        [_sample("A.N0000", day_late), _sample("B.N0000", day_late)],
        {"A.N0000": bars_a, "B.N0000": bars_b},
        sector_map=sector_map,
    )

    early_rel = early[0].x[_feature_index("fp_rel_ret_1d")]
    late_rel = late[0].x[_feature_index("fp_rel_ret_1d")]
    assert math.isfinite(early_rel)
    assert math.isfinite(late_rel)
    assert early_rel != pytest.approx(late_rel)


def test_resolve_sector_map_path_prefers_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    custom = tmp_path / "custom-sector.json"
    custom.write_text('{"A.N0000": "Tech"}', encoding="utf-8")
    monkeypatch.setenv("KOEL_SECTOR_MAP", str(custom))
    assert resolve_sector_map_path() == custom


def test_load_sector_map_for_v2_reads_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    default = tmp_path / "koel-sector-map.json"
    default.write_text('{"Z.N0000": "Banks"}', encoding="utf-8")
    monkeypatch.delenv("KOEL_SECTOR_MAP", raising=False)
    monkeypatch.setattr(
        "koel.ml.feature_pack_v2.DEFAULT_SECTOR_MAP_PATH",
        default,
    )
    sector_map = load_sector_map_for_v2()
    assert sector_map == {"Z.N0000": "Banks"}
