"""SendResult enum + bool adapter for poller send callbacks."""

from __future__ import annotations

from koel.notify import SendResult
from koel.poller import _normalize_send_result


def test_send_result_values() -> None:
    assert SendResult.OK == "ok"
    assert SendResult.DEFERRED == "deferred"
    assert SendResult.FAILED == "failed"


def test_normalize_bool_true_is_ok() -> None:
    assert _normalize_send_result(True) is SendResult.OK


def test_normalize_bool_false_is_failed() -> None:
    """Legacy bool False maps to failed (counts toward dead-letter)."""
    assert _normalize_send_result(False) is SendResult.FAILED


def test_normalize_passthrough_deferred() -> None:
    assert _normalize_send_result(SendResult.DEFERRED) is SendResult.DEFERRED
