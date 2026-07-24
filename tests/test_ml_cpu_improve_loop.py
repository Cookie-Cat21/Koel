"""Improvement-loop grid smoke tests."""

from __future__ import annotations

from koel.ml.cpu_improve_loop import _grid_cycle


def test_each_improve_cycle_emits_1000_configs() -> None:
    for cycle in range(6):
        grid = _grid_cycle(cycle, limit=1000)
        assert len(grid) == 1000
        assert all("kind" in item for item in grid)


def test_improve_cycle_themes_are_distinct() -> None:
    kinds = {_grid_cycle(cycle, limit=1)[0]["kind"] for cycle in range(5)}
    assert "lgb" in kinds
    assert "xgb" in kinds
    assert "blend" in kinds
    assert "lgb_shaped" in kinds
