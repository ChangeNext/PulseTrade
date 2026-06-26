from decimal import Decimal

from app.strategies.base import ComponentSignal, SignalComponent, SignalContext
from app.strategies.technical import average, clamp_score


class MarketRegimeStrategy(SignalComponent):
    name = "market_regime"

    def evaluate(self, context: SignalContext) -> ComponentSignal:
        ready = [item for item in context.market_indices if item.ready]
        if not ready:
            return ComponentSignal(self.name, Decimal("0"), True, "Market proxy data unavailable")
        score = average([item.score for item in ready])
        reason = "; ".join(f"{item.name} {item.score:.0f}" for item in ready)
        return ComponentSignal(self.name, clamp_score(score), True, reason)
