"""Minimal HTTP health check for ops (liveness + last poll status)."""

from __future__ import annotations

import inspect
import json
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Any


def _is_loopback_host(host: object) -> bool:
    # Fail closed — non-strings used to throw on .strip mid health bind
    # (parity web isLoopbackHost typeof guard).
    if not isinstance(host, str):
        return False
    h = host.strip().lower()
    if h.startswith("[") and h.endswith("]"):
        h = h[1:-1]
    return h in ("127.0.0.1", "::1")


def _nonneg_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if value >= 0 else None


def pdf_enrich_hint_from_poller(poller: Any) -> dict[str, int]:
    """Cheap in-memory PDF enrich counters (mock-safe). Empty on failure."""
    fn = getattr(poller, "pdf_enrich_health_snapshot", None)
    if not callable(fn) or inspect.iscoroutinefunction(fn):
        return {}
    try:
        raw = fn()
    except Exception:
        return {}
    if not isinstance(raw, dict):
        return {}
    hint: dict[str, int] = {}
    for key in ("in_flight_tasks", "last_batch_size", "batches_started"):
        parsed = _nonneg_int(raw.get(key))
        if parsed is not None:
            hint[key] = parsed
    return hint


async def pending_briefs_count(storage: Any) -> int | None:
    """Optional SQL pending-briefs count; None when unavailable (fail-soft)."""
    fn = getattr(storage, "count_pending_disclosure_briefs", None)
    if not callable(fn):
        return None
    try:
        raw = await fn() if inspect.iscoroutinefunction(fn) else fn()
    except Exception:
        return None
    return _nonneg_int(raw)


async def brief_queue_health_hint(
    storage: Any | None = None,
    poller: Any | None = None,
) -> dict[str, Any]:
    """Assemble brief/pdf enrich queue hint for loopback health details.

    Never raises. Omits ``pending_briefs`` when the SQL probe is unavailable.
    Does not influence ``ok`` — ops hint only.
    """
    hint: dict[str, Any] = {}
    if poller is not None:
        pdf = pdf_enrich_hint_from_poller(poller)
        if pdf:
            hint["pdf_enrich"] = pdf
    if storage is not None:
        pending = await pending_briefs_count(storage)
        if pending is not None:
            hint["pending_briefs"] = pending
    return hint


class HealthState:
    def __init__(self) -> None:
        self.started_at = datetime.now(UTC).isoformat()
        self.ok = True
        self.details: dict[str, Any] = {}

    def update(self, **kwargs: Any) -> None:
        self.details.update(kwargs)
        if "ok" in kwargs:
            # Fail closed — bool("false")/1 used to mislabel health ok
            # (parity dash === true / row mapper active flags).
            raw_ok = kwargs["ok"]
            if isinstance(raw_ok, bool):
                self.ok = raw_ok


def start_health_server(host: str, port: int, state: HealthState) -> ThreadingHTTPServer:
    outer = state
    loopback = _is_loopback_host(host)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path not in ("/health", "/healthz", "/"):
                self.send_response(404)
                self.end_headers()
                return
            if loopback:
                body: dict[str, Any] = {
                    "status": "ok" if outer.ok else "degraded",
                    "started_at": outer.started_at,
                    **outer.details,
                }
            else:
                # Non-loopback bind: liveness only — no last_error / tick detail.
                body = {
                    "status": "ok" if outer.ok else "degraded",
                    "ok": outer.ok,
                }
            payload = json.dumps(body).encode()
            code = 200 if outer.ok else 503
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

    server = ThreadingHTTPServer((host, port), Handler)
    thread = Thread(target=server.serve_forever, name="health-server", daemon=True)
    thread.start()
    return server
