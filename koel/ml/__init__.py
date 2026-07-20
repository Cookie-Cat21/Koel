"""Offline supervised ML experiments for CSE path data (optional ``[ml]``).

Not wired into the dash/bot until a walk-forward report clears promote gates.
"""

from __future__ import annotations

__all__ = ["sklearn_available"]


def sklearn_available() -> bool:
    try:
        import numpy  # noqa: F401
        import sklearn  # noqa: F401
    except ImportError:
        return False
    return True
