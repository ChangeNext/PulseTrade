from decimal import Decimal

from app.strategies.base import SignalAction, SignalComponent, SignalContext, ScoredSignal
from app.strategies.risk_filter import StrategyRiskFilter


class SignalScorer:
    def __init__(
        self,
        components: tuple[SignalComponent, ...],
        weights: dict[str, Decimal],
        *,
        buy_threshold: Decimal = Decimal("70"),
        sell_threshold: Decimal = Decimal("-60"),
        exit_threshold: Decimal = Decimal("-80"),
        risk_filter: StrategyRiskFilter | None = None,
    ) -> None:
        self.components = components
        self.weights = weights
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold
        self.exit_threshold = exit_threshold
        self.risk_filter = risk_filter or StrategyRiskFilter()

    def evaluate(self, context: SignalContext) -> ScoredSignal:
        signals = tuple(component.evaluate(context) for component in self.components)
        if any(not signal.ready for signal in signals):
            missing = ", ".join(signal.name for signal in signals if not signal.ready)
            return ScoredSignal(context.market.symbol, SignalAction.WAIT, Decimal("0"), signals, f"Waiting for {missing}")
        total_weight = sum(self.weights.get(signal.name, Decimal("0")) for signal in signals)
        score = (
            sum(signal.score * self.weights.get(signal.name, Decimal("0")) for signal in signals)
            / total_weight
            if total_weight > 0
            else Decimal("0")
        )
        if context.already_held and score <= self.exit_threshold:
            action = SignalAction.EXIT
        elif context.already_held and score <= self.sell_threshold:
            action = SignalAction.SELL
        elif score >= self.buy_threshold and self.risk_filter.evaluate(context).can_enter:
            action = SignalAction.BUY
        else:
            action = SignalAction.WAIT
        return ScoredSignal(
            context.market.symbol,
            action,
            score.quantize(Decimal("0.01")),
            signals,
            f"Composite score {score:.2f}",
        )
