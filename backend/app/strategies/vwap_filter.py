from decimal import Decimal

from app.strategies.base import ComponentSignal, SignalComponent, SignalContext


class VWAPFilter(SignalComponent):
    name = "vwap"

    def evaluate(self, context: SignalContext) -> ComponentSignal:
        vwap = context.market.vwap
        if vwap <= 0:
            return ComponentSignal(self.name, Decimal("0"), False, "VWAP unavailable")
        distance_pct = (context.market.price - vwap) / vwap * Decimal("100")
        score = max(Decimal("-100"), min(Decimal("100"), distance_pct * Decimal("100")))
        return ComponentSignal(self.name, score, True, f"Price is {distance_pct:.3f}% from VWAP")
