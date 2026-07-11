"""Storage pool size guard — advisory lock needs a spare connection."""

from __future__ import annotations

import pytest

from chime.storage import Storage


def test_max_size_below_two_rejected() -> None:
    with pytest.raises(ValueError, match="max_size must be >= 2"):
        Storage("postgresql://unused", min_size=1, max_size=1)


def test_max_size_zero_rejected() -> None:
    with pytest.raises(ValueError, match="advisory lock"):
        Storage("postgresql://unused", max_size=0)


def test_max_size_two_accepted() -> None:
    store = Storage("postgresql://unused", min_size=1, max_size=2)
    assert store is not None
