from datetime import datetime, timezone
from decimal import Decimal

from app.strategies.base import MarketIndexSnapshot, MarketSnapshot, PriceBar, SignalContext
from app.strategies.market_regime import MarketRegimeStrategy
from app.strategies.risk_reward import RiskRewardStrategy
from app.strategies.trend_structure import TrendStructureStrategy


def bar(index: int, close: str, *, volume: int = 1000) -> PriceBar:
    price = Decimal(close)
    return PriceBar(
        time=f"09{index:02d}00",
        open=price - Decimal("10"),
        high=price + Decimal("30"),
        low=price - Decimal("30"),
        close=price,
        volume=volume,
    )


def context(
    *,
    intraday: tuple[PriceBar, ...] = (),
    daily: tuple[PriceBar, ...] = (),
    market_indices: tuple[MarketIndexSnapshot, ...] = (),
    price: Decimal = Decimal("1050"),
) -> SignalContext:
    return SignalContext(
        market=MarketSnapshot(
            symbol="005930",
            timestamp=datetime.now(timezone.utc),
            price=price,
            opening_range_high=Decimal("1000"),
            vwap=Decimal("1030"),
            current_volume=3000,
            average_volume=Decimal("1000"),
        ),
        orderbook=None,
        trade_strength=None,
        recent_prices=tuple(item.close for item in intraday),
        intraday_bars=intraday,
        daily_bars=daily,
        market_indices=market_indices,
    )


def test_trend_structure_rewards_higher_highs_and_lows() -> None:
    bars = tuple(bar(index, str(1000 + index * 5)) for index in range(25))
    signal = TrendStructureStrategy().evaluate(context(intraday=bars))
    assert signal.ready is True
    assert signal.score > 0


def test_risk_reward_rewards_near_support_with_room_to_resistance() -> None:
    daily = tuple(
        [
            bar(index, str(990 + index))
            for index in range(10)
        ]
        + [
            PriceBar("10", Decimal("1010"), Decimal("1150"), Decimal("1000"), Decimal("1040"), 1000),
            PriceBar("11", Decimal("1020"), Decimal("1200"), Decimal("1010"), Decimal("1050"), 1000),
        ]
    )
    signal = RiskRewardStrategy().evaluate(context(daily=daily, price=Decimal("1050")))
    assert signal.ready is True
    assert signal.score > 0


def test_market_regime_averages_ready_proxy_scores() -> None:
    indices = (
        MarketIndexSnapshot("KOSPI200 proxy", "069500", Decimal("40000"), Decimal("1"), Decimal("70"), True, "up"),
        MarketIndexSnapshot("KOSDAQ150 proxy", "229200", Decimal("12000"), Decimal("-1"), Decimal("-30"), True, "down"),
    )
    signal = MarketRegimeStrategy().evaluate(context(market_indices=indices))
    assert signal.ready is True
    assert signal.score == Decimal("20")
