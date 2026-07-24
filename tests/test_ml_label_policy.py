"""Material-median label policy keeps only above-median |y_ret| rows."""

from __future__ import annotations

from datetime import date

from koel.ml.cpu_exhaust import _filter_material_median
from koel.ml.dataset import Sample


def _sample(symbol: str, as_of: date, y_ret: float) -> Sample:
    return Sample(
        symbol=symbol,
        as_of=as_of,
        x=(0.0,),
        y_ret=y_ret,
        y_dir=1.0 if y_ret > 0 else -1.0 if y_ret < 0 else 0.0,
        horizon=1,
        target_date=as_of,
    )


def test_filter_material_median_keeps_day_upper_half() -> None:
    day = date(2026, 7, 1)
    rows = [
        _sample("A.N0000", day, 0.01),
        _sample("B.N0000", day, -0.02),
        _sample("C.N0000", day, 0.005),
        _sample("D.N0000", day, 0.03),
    ]
    kept = _filter_material_median(rows)
    symbols = {sample.symbol for sample in kept}
    assert symbols == {"B.N0000", "D.N0000"}
