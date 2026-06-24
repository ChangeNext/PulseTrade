from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.kis.market import MinuteBar
from app.strategies.runtime import SymbolBars


def test_symbol_bars_builds_five_minute_orb_vwap_snapshot() -> None:
    series = SymbolBars()
    for minute in range(30):
        hour = 9 + minute // 60
        minute_of_hour = minute % 60
        key = f"{hour:02d}{minute_of_hour:02d}00"
        price = Decimal(70000 + minute * 100)
        series.bars[key] = MinuteBar(
            symbol="005930",
            time=key,
            price=price,
            high=price + 100,
            low=price - 100,
            volume=100 + minute,
        )
    snapshot = series.snapshot(
        "005930", datetime(2026, 6, 24, 9, 29, tzinfo=timezone(timedelta(hours=9)))
    )
    assert snapshot is not None
    assert snapshot.opening_range_high == Decimal("70500")
    assert snapshot.current_volume == 129
    assert snapshot.average_volume > 0
