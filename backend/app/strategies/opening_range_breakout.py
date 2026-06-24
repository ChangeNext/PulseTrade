from decimal import Decimal

from app.strategies.base import ComponentSignal, SignalComponent, SignalContext


class ORBStrategy(SignalComponent):
    name = "opening_range_breakout"

    def evaluate(self, context: SignalContext) -> ComponentSignal:
        high = context.market.opening_range_high
        if high <= 0:
            return ComponentSignal(self.name, Decimal("0"), False, "Opening range unavailable")
        distance_pct = (context.market.price - high) / high * Decimal("100")
        score = max(Decimal("-100"), min(Decimal("100"), distance_pct * Decimal("125")))
        return ComponentSignal(self.name, score, True, f"Price is {distance_pct:.3f}% from ORB high")
