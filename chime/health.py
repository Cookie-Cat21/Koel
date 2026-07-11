"""Minimal HTTP health check for ops (liveness + last poll status)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Any


def _is_loopback_host(host: str) -> bool:
    h = host.strip().lower()
    if h.startswith("[") and h.endswith("]"):
        h = h[1:-1]
    return h in ("127.0.0.1", "::1")


class HealthState:
    def __init__(self) -> None:
        self.started_at = datetime.now(UTC).isoformat()
        self.ok = True
        self.details: dict[str, Any] = {}

    def update(self, **kwargs: Any) -> None:
        self.details.update(kwargs)
        if "ok" in kwargs:
            self.ok = bool(kwargs["ok"])


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
