from decimal import Decimal

from app.kis.market import MinuteBar
from app.main import aggregate_minute_bars


def test_aggregate_minute_bars_groups_ohlcv_by_ten_minutes() -> None:
    bars = [
        MinuteBar("005930", "090100", Decimal("100"), Decimal("101"), Decimal("99"), 10, Decimal("100")),
        MinuteBar("005930", "090900", Decimal("104"), Decimal("105"), Decimal("98"), 20, Decimal("101")),
        MinuteBar("005930", "091000", Decimal("107"), Decimal("108"), Decimal("106"), 30, Decimal("107")),
    ]

    aggregated = aggregate_minute_bars(bars, 10)

    assert [bar.time for bar in aggregated] == ["090000", "091000"]
    assert aggregated[0].open == Decimal("100")
    assert aggregated[0].price == Decimal("104")
    assert aggregated[0].high == Decimal("105")
    assert aggregated[0].low == Decimal("98")
    assert aggregated[0].volume == 30
