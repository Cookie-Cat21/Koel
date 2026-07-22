"""Unit tests for CSE STOMP frame helpers + payload mappers."""

from __future__ import annotations

from datetime import UTC, datetime

from koel.adapters.cse_stomp import (
    TOPIC_ASPI,
    daytrade_rows_to_snapshots,
    index_payload_to_snapshot,
    parse_stomp_frame,
    sockjs_ws_url,
    status_payload_to_text,
    stomp_frame,
    summary_payload_to_daily_row,
    today_share_rows_to_snapshots,
)


def test_stomp_frame_null_terminated() -> None:
    frame = stomp_frame("SEND", {"destination": "/app/request-aspi", "content-length": "0"})
    assert frame.startswith("SEND\n")
    assert frame.endswith("\x00")
    assert "destination:/app/request-aspi" in frame


def test_parse_stomp_message_frame() -> None:
    raw = (
        "MESSAGE\n"
        "destination:/topic/aspi\n"
        "content-type:application/json\n"
        "\n"
        '{"value":1.0,"change":0.1}\x00'
    )
    parsed = parse_stomp_frame(raw)
    assert parsed is not None
    command, headers, body = parsed
    assert command == "MESSAGE"
    assert headers["destination"] == TOPIC_ASPI
    assert '"value":1.0' in body


def test_sockjs_ws_url_shape() -> None:
    url = sockjs_ws_url("https://www.cse.lk/api/ws")
    assert url.startswith("wss://www.cse.lk/api/ws/")
    assert url.endswith("/websocket")


def test_index_payload_iso_timestamp() -> None:
    snap = index_payload_to_snapshot(
        {
            "id": 1,
            "value": 21239.85,
            "change": 94.12,
            "percentage": 0.445,
            "timestamp": "2026-07-22T05:55:56.440+0000",
        },
        default_code="ASPI",
        default_name="All Share Price Index",
    )
    assert snap is not None
    assert snap.code == "ASPI"
    assert snap.value == 21239.85
    assert abs((snap.change_pct or 0) - 0.445) < 1e-9
    assert snap.ts == datetime(2026, 7, 22, 5, 55, 56, 440000, tzinfo=UTC)


def test_today_share_and_daytrade_mappers() -> None:
    today = today_share_rows_to_snapshots(
        [
            {
                "id": 204,
                "symbol": "aban.n0000",
                "open": 1060.0,
                "high": 1060.0,
                "low": 1060.0,
                "lastTradedPrice": 1060.0,
                "change": 13.5,
                "changePercentage": 1.29,
                "quantity": 2,
                "tradesTime": "2026-07-22T05:45:07.386+0000",
            }
        ]
    )
    assert len(today) == 1
    assert today[0].symbol == "ABAN.N0000"
    assert today[0].price == 1060.0
    assert today[0].cse_stock_id == 204

    day = daytrade_rows_to_snapshots(
        [{"symbol": "JKH.N0000", "price": 19.7, "change": 0.1, "changePercentage": 0.5}]
    )
    assert len(day) == 1
    assert day[0].symbol == "JKH.N0000"
    assert day[0].change_pct == 0.5


def test_summary_and_status_mappers() -> None:
    row = summary_payload_to_daily_row(
        {
            "id": 1,
            "tradeVolume": 2.7e9,
            "shareVolume": 63442223,
            "tradeDate": "2026-07-22T05:55:56.440+0000",
            "trades": 5291,
        }
    )
    assert row is not None
    assert row["trade_date"].isoformat() == "2026-07-22"
    assert row["market_turnover"] == 2.7e9
    assert row["market_trades"] == 5291.0
    assert status_payload_to_text({"status": "Market Open"}) == "Market Open"
    assert status_payload_to_text("Market Closed") == "Market Closed"
