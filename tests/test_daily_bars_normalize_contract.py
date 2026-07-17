"""Contract mirror for web daily-bars OHLC normalize (flat candle fill)."""


def normalize_daily_bar(row: dict) -> dict | None:
    trade_date = row.get("trade_date")
    if not isinstance(trade_date, str) or len(trade_date) < 10:
        return None
    close = row.get("close", row.get("price"))
    if not isinstance(close, (int, float)) or isinstance(close, bool):
        return None
    close_f = float(close)
    if close_f <= 0:
        return None
    open_v = row.get("open")
    high_v = row.get("high")
    low_v = row.get("low")
    open_f = (
        float(open_v)
        if isinstance(open_v, (int, float)) and not isinstance(open_v, bool)
        else close_f
    )
    high_f = (
        float(high_v)
        if isinstance(high_v, (int, float)) and not isinstance(high_v, bool)
        else max(open_f, close_f)
    )
    low_f = (
        float(low_v)
        if isinstance(low_v, (int, float)) and not isinstance(low_v, bool)
        else min(open_f, close_f)
    )
    high_f = max(high_f, open_f, close_f)
    low_f = min(low_f, open_f, close_f)
    return {
        "trade_date": trade_date[:10],
        "open": open_f,
        "high": high_f,
        "low": low_f,
        "close": close_f,
    }


def test_flat_synthesis() -> None:
    b = normalize_daily_bar({"trade_date": "2026-07-16", "price": 17.3})
    assert b is not None
    assert b["open"] == b["high"] == b["low"] == b["close"] == 17.3


def test_rejects_zero_close() -> None:
    assert normalize_daily_bar({"trade_date": "2026-07-16", "price": 0}) is None


def test_full_ohlc() -> None:
    b = normalize_daily_bar(
        {
            "trade_date": "2026-07-16",
            "open": 10,
            "high": 12,
            "low": 9,
            "price": 11,
        }
    )
    assert b == {
        "trade_date": "2026-07-16",
        "open": 10.0,
        "high": 12.0,
        "low": 9.0,
        "close": 11.0,
    }
