"""CSE STOMP-over-SockJS client (``https://www.cse.lk/api/ws``).

Mirrors the official cse.lk Next.js live topics. Prefer HTTP ``tradeSummary``
for the full board / alert spine; use this feed for live indexes, session
status/summary, day-tape ticks, and the short today-sharePrice slice.

Unofficial · polite · NFA. Not affiliated with CSE.
"""

from __future__ import annotations

import asyncio
import json
import math
import random
import string
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import urlparse

from koel.adapters.cse import _finite_or_none
from koel.domain import IndexSnapshot, PriceSnapshot
from koel.logging_setup import get_logger

log = get_logger(__name__)

DEFAULT_WS_HTTP_BASE = "https://www.cse.lk/api/ws"

TOPIC_ASPI = "/topic/aspi"
TOPIC_SNP = "/topic/snp"
TOPIC_STATUS = "/topic/status"
TOPIC_SUMMARY = "/topic/summary"
TOPIC_TODAY_SHARE = "/topic/today-sharePrice"
TOPIC_TOP_GAINERS = "/topic/top-gainers"
TOPIC_TOP_LOSERS = "/topic/top-looses"
TOPIC_MOST_ACTIVE = "/topic/most-active-trades"
TOPIC_DAYTRADE = "/topic/daytrade"

REQUEST_BY_TOPIC: dict[str, str] = {
    TOPIC_ASPI: "/app/request-aspi",
    TOPIC_SNP: "/app/request-snp",
    TOPIC_STATUS: "/app/request-status",
    TOPIC_SUMMARY: "/app/request-summary",
    TOPIC_TODAY_SHARE: "/app/request-today-sharePrice",
    TOPIC_TOP_GAINERS: "/app/request-top-gainers",
    TOPIC_TOP_LOSERS: "/app/request-top-looses",
    TOPIC_MOST_ACTIVE: "/app/request-most-active-trades",
    TOPIC_DAYTRADE: "/app/request-daytrade",
}

MessageHandler = Callable[[str, Any], Awaitable[None] | None]


def _sid(n: int = 8) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(random.choice(alphabet) for _ in range(n))


def stomp_frame(
    command: str,
    headers: dict[str, str] | None = None,
    body: str = "",
) -> str:
    """Build a STOMP 1.x frame terminated with a null octet."""
    lines = [command]
    for key, value in (headers or {}).items():
        lines.append(f"{key}:{value}")
    lines.append("")
    return "\n".join(lines) + "\n" + body + "\x00"


def parse_stomp_frame(raw: str) -> tuple[str, dict[str, str], str] | None:
    """Return ``(command, headers, body)`` or ``None`` if unusable."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.rstrip("\x00")
    if "\n\n" in text:
        head, body = text.split("\n\n", 1)
    else:
        head, body = text, ""
    lines = head.split("\n")
    if not lines or not lines[0].strip():
        return None
    command = lines[0].strip()
    headers: dict[str, str] = {}
    for line in lines[1:]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        headers[key.strip()] = value.strip()
    return command, headers, body


def _parse_ts(raw: Any, *, fallback: datetime | None = None) -> datetime:
    """Accept CSE ms epoch, ISO strings, or fall back to ``now``/provided."""
    fb = fallback or datetime.now(UTC)
    if isinstance(raw, bool):
        return fb
    if isinstance(raw, (int, float)) and math.isfinite(float(raw)):
        try:
            return datetime.fromtimestamp(float(raw) / 1000.0, tz=UTC)
        except (OverflowError, ValueError, OSError):
            return fb
    if isinstance(raw, str) and raw.strip():
        text = raw.strip()
        # CSE sometimes ships +0000 instead of +00:00
        if len(text) >= 5 and (text[-5] in "+-") and text[-3] != ":":
            text = text[:-2] + ":" + text[-2:]
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return fb
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    return fb


def index_payload_to_snapshot(
    payload: Any,
    *,
    default_code: str,
    default_name: str,
    now: datetime | None = None,
) -> IndexSnapshot | None:
    """Normalize ASPI/SNP STOMP JSON into ``IndexSnapshot``."""
    if not isinstance(payload, dict):
        return None
    value = payload.get("value", payload.get("indexValue"))
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(float(value)):
        return None
    code_raw = payload.get("code") or payload.get("indexCode") or default_code
    if not isinstance(code_raw, str) or not code_raw.strip():
        return None
    name_raw = payload.get("name") or payload.get("indexName") or default_name
    name = (
        name_raw.strip()
        if isinstance(name_raw, str) and name_raw.strip()
        else default_name
    )
    pct = payload.get("percentage")
    if pct is None:
        pct = payload.get("percentageChange", payload.get("changePct"))
    change = payload.get("change")
    return IndexSnapshot(
        code=code_raw.strip().upper(),
        name=name,
        value=float(value),
        change=_finite_or_none(
            float(change) if isinstance(change, (int, float)) and not isinstance(change, bool) else None
        ),
        change_pct=_finite_or_none(
            float(pct) if isinstance(pct, (int, float)) and not isinstance(pct, bool) else None
        ),
        ts=_parse_ts(payload.get("timestamp", payload.get("transactionTime")), fallback=now),
    )


def today_share_rows_to_snapshots(
    payload: Any, *, now: datetime | None = None
) -> list[PriceSnapshot]:
    """Normalize ``/topic/today-sharePrice`` array (short board slice)."""
    if not isinstance(payload, list):
        return []
    fb = now or datetime.now(UTC)
    out: list[PriceSnapshot] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        symbol = item.get("symbol")
        if not isinstance(symbol, str) or not symbol.strip():
            continue
        price = item.get("lastTradedPrice", item.get("price"))
        if isinstance(price, bool) or not isinstance(price, (int, float)):
            continue
        if not math.isfinite(float(price)):
            continue
        cse_id = item.get("id")
        if isinstance(cse_id, bool) or not isinstance(cse_id, int) or cse_id <= 0:
            cse_id = None
        out.append(
            PriceSnapshot(
                symbol=symbol.strip().upper(),
                price=float(price),
                change=_finite_or_none(
                    float(item["change"])
                    if isinstance(item.get("change"), (int, float))
                    and not isinstance(item.get("change"), bool)
                    else None
                ),
                change_pct=_finite_or_none(
                    float(item["changePercentage"])
                    if isinstance(item.get("changePercentage"), (int, float))
                    and not isinstance(item.get("changePercentage"), bool)
                    else None
                ),
                volume=_finite_or_none(
                    float(item["quantity"])
                    if isinstance(item.get("quantity"), (int, float))
                    and not isinstance(item.get("quantity"), bool)
                    else None
                ),
                crossing_volume=_finite_or_none(
                    float(item["crossingVolume"])
                    if isinstance(item.get("crossingVolume"), (int, float))
                    and not isinstance(item.get("crossingVolume"), bool)
                    else None
                ),
                high=_finite_or_none(
                    float(item["high"])
                    if isinstance(item.get("high"), (int, float))
                    and not isinstance(item.get("high"), bool)
                    else None
                ),
                low=_finite_or_none(
                    float(item["low"])
                    if isinstance(item.get("low"), (int, float))
                    and not isinstance(item.get("low"), bool)
                    else None
                ),
                open=_finite_or_none(
                    float(item["open"])
                    if isinstance(item.get("open"), (int, float))
                    and not isinstance(item.get("open"), bool)
                    else None
                ),
                ts=_parse_ts(item.get("tradesTime"), fallback=fb),
                cse_stock_id=cse_id,
            )
        )
    return out


def daytrade_rows_to_snapshots(
    payload: Any, *, now: datetime | None = None
) -> list[PriceSnapshot]:
    """Normalize ``/topic/daytrade`` last-print ticks into thin snapshots."""
    if not isinstance(payload, list):
        return []
    fb = now or datetime.now(UTC)
    out: list[PriceSnapshot] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        symbol = item.get("symbol")
        if not isinstance(symbol, str) or not symbol.strip():
            continue
        price = item.get("price")
        if isinstance(price, bool) or not isinstance(price, (int, float)):
            continue
        if not math.isfinite(float(price)):
            continue
        out.append(
            PriceSnapshot(
                symbol=symbol.strip().upper(),
                price=float(price),
                change=_finite_or_none(
                    float(item["change"])
                    if isinstance(item.get("change"), (int, float))
                    and not isinstance(item.get("change"), bool)
                    else None
                ),
                change_pct=_finite_or_none(
                    float(item["changePercentage"])
                    if isinstance(item.get("changePercentage"), (int, float))
                    and not isinstance(item.get("changePercentage"), bool)
                    else None
                ),
                ts=fb,
            )
        )
    return out


def summary_payload_to_daily_row(payload: Any) -> dict[str, Any] | None:
    """Map session ``/topic/summary`` into a ``market_daily_summary`` upsert dict."""
    if not isinstance(payload, dict):
        return None
    ts = _parse_ts(payload.get("tradeDate"))
    trade_date = ts.astimezone(UTC).date() if isinstance(ts, datetime) else date.today()
    turnover = payload.get("tradeVolume")
    trades = payload.get("trades")
    share_vol = payload.get("shareVolume")
    return {
        "trade_date": trade_date,
        "market_turnover": (
            float(turnover)
            if isinstance(turnover, (int, float)) and not isinstance(turnover, bool)
            and math.isfinite(float(turnover))
            else None
        ),
        "market_trades": (
            float(trades)
            if isinstance(trades, (int, float)) and not isinstance(trades, bool)
            and math.isfinite(float(trades))
            else None
        ),
        "equity_foreign_purchase": None,
        "equity_foreign_sales": None,
        "foreign_net": None,
        "volume_of_turnover": (
            float(share_vol)
            if isinstance(share_vol, (int, float)) and not isinstance(share_vol, bool)
            and math.isfinite(float(share_vol))
            else None
        ),
        "market_cap": None,
        "asi": None,
        "raw": {"source": "stomp_summary", **payload},
    }


def status_payload_to_text(payload: Any) -> str | None:
    """Extract market status string (e.g. ``Market Open`` / ``Market Closed``)."""
    if isinstance(payload, str) and payload.strip():
        return payload.strip()
    if isinstance(payload, dict):
        status = payload.get("status")
        if isinstance(status, str) and status.strip():
            return status.strip()
    return None


def sockjs_ws_url(http_base: str = DEFAULT_WS_HTTP_BASE) -> str:
    """Build a SockJS websocket transport URL for the CSE broker."""
    base = (http_base or DEFAULT_WS_HTTP_BASE).rstrip("/")
    parsed = urlparse(base)
    scheme = "wss" if parsed.scheme in {"https", "wss"} else "ws"
    host_path = parsed.netloc + parsed.path.rstrip("/")
    return f"{scheme}://{host_path}/{_sid(3)}/{_sid(8)}/websocket"


class CseStompClient:
    """Long-lived SockJS + STOMP session with reconnect + topic fan-out."""

    def __init__(
        self,
        *,
        http_base: str = DEFAULT_WS_HTTP_BASE,
        on_message: MessageHandler | None = None,
        topics: list[str] | None = None,
        rerequest_seconds: float = 20.0,
        reconnect_min_seconds: float = 2.0,
        reconnect_max_seconds: float = 60.0,
        origin: str = "https://www.cse.lk",
    ) -> None:
        self.http_base = http_base.rstrip("/") if http_base else DEFAULT_WS_HTTP_BASE
        self.on_message = on_message
        self.topics = list(topics or REQUEST_BY_TOPIC.keys())
        self.rerequest_seconds = max(5.0, float(rerequest_seconds))
        self.reconnect_min_seconds = max(0.5, float(reconnect_min_seconds))
        self.reconnect_max_seconds = max(
            self.reconnect_min_seconds, float(reconnect_max_seconds)
        )
        self.origin = origin
        self._stop = asyncio.Event()
        self._task: asyncio.Task[Any] | None = None
        self.connected = False
        self.last_message_at: datetime | None = None
        self.last_error: str | None = None
        self.messages_ok: int = 0

    def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run_forever(), name="cse-stomp")

    async def stop(self) -> None:
        self._stop.set()
        task = self._task
        self._task = None
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                log.exception("cse_stomp_stop_error")
        self.connected = False

    async def _run_forever(self) -> None:
        delay = self.reconnect_min_seconds
        while not self._stop.is_set():
            try:
                await self._session()
                delay = self.reconnect_min_seconds
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.connected = False
                self.last_error = str(exc)[:240]
                log.warning("cse_stomp_session_failed", error=self.last_error)
            if self._stop.is_set():
                break
            await asyncio.sleep(delay)
            delay = min(self.reconnect_max_seconds, delay * 1.7)

    async def _session(self) -> None:
        try:
            import websockets
        except ImportError as exc:  # pragma: no cover - dependency gate
            raise RuntimeError(
                "websockets package required for CSE_STOMP_ENABLED=1"
            ) from exc

        url = sockjs_ws_url(self.http_base)
        headers = {
            "Origin": self.origin,
            "Referer": f"{self.origin}/",
            "User-Agent": (
                "Mozilla/5.0 (compatible; koel-stomp/0.1; +https://github.com/ArdenoStudio/Koel)"
            ),
        }
        log.info("cse_stomp_connecting", url=url.rsplit("/", 3)[0] + "/…/websocket")
        async with websockets.connect(
            url,
            additional_headers=headers,
            open_timeout=20,
            max_size=8_000_000,
            ping_interval=None,
        ) as ws:
            open_frame = await asyncio.wait_for(ws.recv(), timeout=15)
            if open_frame != "o":
                raise RuntimeError(f"unexpected SockJS open frame: {open_frame!r}")
            await ws.send(
                json.dumps(
                    [
                        stomp_frame(
                            "CONNECT",
                            {
                                "accept-version": "1.1,1.2",
                                "host": urlparse(self.origin).netloc or "www.cse.lk",
                                "heart-beat": "0,0",
                            },
                        )
                    ]
                )
            )
            connected = False
            next_request = 0.0
            while not self._stop.is_set():
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=5)
                except TimeoutError:
                    if connected and asyncio.get_running_loop().time() >= next_request:
                        await self._request_all(ws)
                        next_request = (
                            asyncio.get_running_loop().time() + self.rerequest_seconds
                        )
                    continue
                if raw == "h":
                    continue
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8", errors="replace")
                if not isinstance(raw, str):
                    continue
                if raw.startswith("c"):
                    raise RuntimeError(f"SockJS close: {raw[:160]}")
                if not raw.startswith("a"):
                    continue
                try:
                    frames = json.loads(raw[1:])
                except json.JSONDecodeError:
                    continue
                if not isinstance(frames, list):
                    continue
                for frame in frames:
                    if not isinstance(frame, str):
                        continue
                    parsed = parse_stomp_frame(frame)
                    if parsed is None:
                        continue
                    command, headers, body = parsed
                    if command == "CONNECTED":
                        if not connected:
                            connected = True
                            self.connected = True
                            self.last_error = None
                            await self._subscribe_all(ws)
                            await self._request_all(ws)
                            next_request = (
                                asyncio.get_running_loop().time()
                                + self.rerequest_seconds
                            )
                            log.info("cse_stomp_connected", topics=len(self.topics))
                        continue
                    if command == "ERROR":
                        self.last_error = (headers.get("message") or body)[:240]
                        raise RuntimeError(f"STOMP ERROR: {self.last_error}")
                    if command != "MESSAGE":
                        continue
                    dest = headers.get("destination") or ""
                    payload: Any
                    try:
                        payload = json.loads(body) if body.strip() else None
                    except json.JSONDecodeError:
                        payload = body
                    self.last_message_at = datetime.now(UTC)
                    self.messages_ok += 1
                    if self.on_message is not None:
                        result = self.on_message(dest, payload)
                        if asyncio.iscoroutine(result):
                            await result

    async def _subscribe_all(self, ws: Any) -> None:
        for i, topic in enumerate(self.topics):
            await ws.send(
                json.dumps(
                    [
                        stomp_frame(
                            "SUBSCRIBE",
                            {
                                "id": f"koel-sub-{i}",
                                "destination": topic,
                                "ack": "auto",
                            },
                        )
                    ]
                )
            )

    async def _request_all(self, ws: Any) -> None:
        for topic in self.topics:
            app = REQUEST_BY_TOPIC.get(topic)
            if not app:
                continue
            await ws.send(
                json.dumps(
                    [
                        stomp_frame(
                            "SEND",
                            {"destination": app, "content-length": "0"},
                        )
                    ]
                )
            )
