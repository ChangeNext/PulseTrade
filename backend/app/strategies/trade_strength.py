from decimal import Decimal

from app.strategies.base import ComponentSignal, SignalComponent, SignalContext


class TradeStrengthStrategy(SignalComponent):
    name = "trade_strength"

    def evaluate(self, context: SignalContext) -> ComponentSignal:
        strength = context.trade_strength
        if strength is None or strength <= 0:
            return ComponentSignal(self.name, Decimal("0"), False, "Trade strength unavailable")
        score = max(Decimal("-100"), min(Decimal("100"), (strength - Decimal("100")) * Decimal("2")))
        return ComponentSignal(self.name, score, True, f"Trade strength is {strength:.2f}")
