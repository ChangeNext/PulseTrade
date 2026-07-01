from decimal import Decimal

import pytest

from app.config import Settings
from app.kis.market import MinuteBar, Quote
from app.scanner import StockScanner
from app.strategies.base import OrderBookSnapshot


class FakeMarket:
    async def get_current_price(self, symbol: str) -> Quote:
        return {
            "005930": Quote(
                symbol="005930",
                name="Samsung Electronics",
                price=Decimal("75000"),
                volume=10_000_000,
                change_pct=Decimal("2.5"),
                trade_value=Decimal("750000000000"),
            ),
            "000660": Quote(
                symbol="000660",
                name="SK hynix",
                price=Decimal("280000"),
                volume=100_000,
                change_pct=Decimal("15"),
                trade_value=Decimal("1000000000"),
            ),
        }[symbol]

    async def get_minute_bars(self, symbol: str, *, max_pages: int = 4) -> list[MinuteBar]:
        if symbol == "005930":
            return [
                MinuteBar(symbol, f"090{index:03d}", Decimal("74000"), Decimal("74100"), Decimal("73900"), 1000)
                for index in range(20)
            ] + [MinuteBar(symbol, "092000", Decimal("75000"), Decimal("75100"), Decimal("74900"), 3000)]
        return [
            MinuteBar(symbol, f"090{index:03d}", Decimal("280000"), Decimal("281000"), Decimal("279000"), 100)
            for index in range(21)
        ]

    async def get_orderbook(self, symbol: str) -> OrderBookSnapshot:
        if symbol == "005930":
            return OrderBookSnapshot(Decimal("75000"), Decimal("74900"), 10000, 12000)
        return OrderBookSnapshot(Decimal("281000"), Decimal("279000"), 100, 100)

    async def is_vi_active(self, symbol: str) -> bool:
        return False


@pytest.mark.asyncio
async def test_scanner_passes_liquid_vwap_volume_candidates() -> None:
    settings = Settings(
        scanner_symbols="005930,000660",
        scanner_min_trade_value_krw=30_000_000_000,
        scanner_min_volume_spike=1.3,
        scanner_min_change_pct=0.2,
        scanner_max_change_pct=12.0,
        scanner_max_spread_bps=20.0,
        scanner_max_candidates=5,
    )
    rows = await StockScanner(settings, FakeMarket()).scan()

    assert rows[0].symbol == "005930"
    assert rows[0].passed
    assert rows[0].volume_spike == Decimal("3")
    assert not rows[0].reasons
    assert rows[1].symbol == "000660"
    assert not rows[1].passed
    assert "LOW_TRADE_VALUE" in rows[1].reasons
    assert "OVERHEATED_CHANGE_RATE" in rows[1].reasons
