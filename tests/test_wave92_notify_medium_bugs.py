"""Wave92: medium+ circuit breaker constructor invariants.

Direct ``CircuitBreaker`` construction used to accept poisoned numeric knobs.
That could mask the real upstream exception during ``call`` failure handling
(``1 >= "5"``) or wedge an open circuit forever with ``reset_timeout=nan``.
"""

from __future__ import annotations

import math
import time

import pytest

from chime.circuit import CircuitBreaker, CircuitState


@pytest.mark.asyncio
async def test_circuit_bad_fail_max_does_not_mask_upstream_exception() -> None:
    cb = CircuitBreaker(name="api", fail_max="5", reset_timeout=60.0)  # type: ignore[arg-type]

    async def bad() -> None:
        raise RuntimeError("upstream down")

    with pytest.raises(RuntimeError, match="upstream down"):
        await cb.call(bad)

    assert cb.fail_max == 5
    assert cb._failures == 1
    assert cb.state == CircuitState.CLOSED


def test_circuit_nonfinite_reset_timeout_fails_closed_to_default() -> None:
    cb = CircuitBreaker(name="api", fail_max=1, reset_timeout=math.nan)
    cb.record_failure()

    assert cb.reset_timeout == 60.0
    assert cb.state == CircuitState.OPEN
    cb._opened_at = time.monotonic() - 61.0
    assert cb.state == CircuitState.HALF_OPEN
