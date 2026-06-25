from datetime import datetime, timezone
from decimal import Decimal

from app.strategies.base import MarketSnapshot, SignalContext
from app.strategies.trend_alignment import TrendAlignmentStrategy


def context(prices: tuple[Decimal, ...]) -> SignalContext:
    return SignalContext(
        market=MarketSnapshot(
            symbol="005930",
            timestamp=datetime.now(timezone.utc),
            price=prices[-1],
            opening_range_high=Decimal("70000"),
            vwap=Decimal("70500"),
            current_volume=3000,
            average_volume=Decimal("1000"),
        ),
        orderbook=None,
        trade_strength=None,
        recent_prices=prices,
    )


def test_trend_alignment_scores_rising_price_structure_positive() -> None:
    prices = tuple(Decimal(70000 + index * 70) for index in range(25))
    signal = TrendAlignmentStrategy().evaluate(context(prices))
    assert signal.ready is True
    assert signal.score > 0


def test_trend_alignment_scores_falling_price_structure_negative() -> None:
    prices = tuple(Decimal(72000 - index * 70) for index in range(25))
    signal = TrendAlignmentStrategy().evaluate(context(prices))
    assert signal.ready is True
    assert signal.score < 0


def test_trend_alignment_waits_for_enough_history() -> None:
    prices = tuple(Decimal(70000 + index * 70) for index in range(10))
    signal = TrendAlignmentStrategy().evaluate(context(prices))
    assert signal.ready is False
