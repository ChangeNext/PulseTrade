from datetime import datetime, timezone
from decimal import Decimal

from app.strategies.base import (
    ComponentSignal,
    MarketSnapshot,
    OrderBookSnapshot,
    SignalAction,
    SignalComponent,
    SignalContext,
)
from app.strategies.signal_scorer import SignalScorer


class FixedComponent(SignalComponent):
    def __init__(self, name: str, score: str, ready: bool = True) -> None:
        self.name = name
        self.score = Decimal(score)
        self.ready = ready

    def evaluate(self, context: SignalContext) -> ComponentSignal:
        return ComponentSignal(self.name, self.score, self.ready, self.name)


def context(*, held: bool = False) -> SignalContext:
    return SignalContext(
        market=MarketSnapshot(
            symbol="005930",
            timestamp=datetime.now(timezone.utc),
            price=Decimal("71000"),
            opening_range_high=Decimal("70000"),
            vwap=Decimal("70500"),
            current_volume=3000,
            average_volume=Decimal("1000"),
        ),
        orderbook=OrderBookSnapshot(
            Decimal("71100"), Decimal("71000"), 100, 300,
            received_at=datetime.now(timezone.utc),
        ),
        trade_strength=Decimal("130"),
        recent_prices=tuple(Decimal(70000 + index * 100) for index in range(10)),
        already_held=held,
    )


def test_signal_scorer_emits_buy_above_threshold() -> None:
    scorer = SignalScorer(
        (FixedComponent("a", "80"), FixedComponent("b", "90")),
        {"a": Decimal("50"), "b": Decimal("50")},
    )
    assert scorer.evaluate(context()).action == SignalAction.BUY


def test_signal_scorer_waits_for_missing_component() -> None:
    scorer = SignalScorer(
        (FixedComponent("a", "100"), FixedComponent("b", "0", ready=False)),
        {"a": Decimal("50"), "b": Decimal("50")},
    )
    assert scorer.evaluate(context()).action == SignalAction.WAIT


def test_signal_scorer_emits_exit_for_strong_bearish_held_position() -> None:
    scorer = SignalScorer(
        (FixedComponent("a", "-90"),), {"a": Decimal("100")}
    )
    assert scorer.evaluate(context(held=True)).action == SignalAction.EXIT


def test_signal_scorer_blocks_buy_when_spread_is_too_wide() -> None:
    base = context()
    wide = SignalContext(
        market=base.market,
        orderbook=OrderBookSnapshot(
            Decimal("72000"), Decimal("70000"), 100, 300,
            received_at=datetime.now(timezone.utc),
        ),
        trade_strength=base.trade_strength,
        recent_prices=base.recent_prices,
    )
    scorer = SignalScorer((FixedComponent("a", "100"),), {"a": Decimal("100")})
    assert scorer.evaluate(wide).action == SignalAction.WAIT
