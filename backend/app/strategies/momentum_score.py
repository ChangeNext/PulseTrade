from decimal import Decimal

from app.strategies.base import ComponentSignal, SignalComponent, SignalContext


class MomentumScore(SignalComponent):
    name = "momentum"

    def __init__(self, lookback: int = 5) -> None:
        self.lookback = lookback

    def evaluate(self, context: SignalContext) -> ComponentSignal:
        prices = context.recent_prices
        if len(prices) < self.lookback + 1 or prices[-self.lookback - 1] <= 0:
            return ComponentSignal(self.name, Decimal("0"), False, "Momentum history unavailable")
        baseline = prices[-self.lookback - 1]
        change_pct = (prices[-1] - baseline) / baseline * Decimal("100")
        score = max(Decimal("-100"), min(Decimal("100"), change_pct * Decimal("50")))
        return ComponentSignal(self.name, score, True, f"{self.lookback}-minute momentum is {change_pct:.3f}%")
