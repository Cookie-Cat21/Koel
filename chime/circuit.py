"""Minimal async-friendly circuit breaker for flaky upstreams."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeVar

T = TypeVar("T")


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(RuntimeError):
    """Raised when the circuit is open and calls are short-circuited."""


@dataclass
class CircuitBreaker:
    name: str
    fail_max: int = 5
    reset_timeout: float = 60.0
    _failures: int = 0
    _opened_at: float | None = None
    _state: CircuitState = CircuitState.CLOSED
    _half_open_trial: bool = False
    _lock_note: str = field(default="", repr=False)

    @property
    def state(self) -> CircuitState:
        if (
            self._state == CircuitState.OPEN
            and self._opened_at is not None
            and time.monotonic() - self._opened_at >= self.reset_timeout
        ):
            self._state = CircuitState.HALF_OPEN
            self._half_open_trial = False
        return self._state

    def snapshot(self) -> dict[str, Any]:
        """Ops-facing metrics for loopback /health details (E8-C01)."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failures": self._failures,
            "fail_max": self.fail_max,
            "reset_timeout_seconds": self.reset_timeout,
            "half_open_trial": self._half_open_trial,
        }

    def _before_call(self) -> None:
        state = self.state
        if state == CircuitState.OPEN:
            raise CircuitOpenError(f"circuit open: {self.name}")
        if state == CircuitState.HALF_OPEN and self._half_open_trial:
            raise CircuitOpenError(f"circuit half-open busy: {self.name}")
        if state == CircuitState.HALF_OPEN:
            self._half_open_trial = True

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None
        self._half_open_trial = False
        self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        self._failures += 1
        self._half_open_trial = False
        if self._failures >= self.fail_max or self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
            self._opened_at = time.monotonic()

    async def call(self, fn: Callable[[], Awaitable[T]]) -> T:
        self._before_call()
        try:
            result = await fn()
        except Exception:
            self.record_failure()
            raise
        self.record_success()
        return result
