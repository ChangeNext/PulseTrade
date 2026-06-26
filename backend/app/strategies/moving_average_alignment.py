from decimal import Decimal

from app.strategies.base import ComponentSignal, SignalComponent, SignalContext
from app.strategies.technical import clamp_score, pct_change, sma


class MovingAverageAlignmentStrategy(SignalComponent):
    name = "moving_average_alignment"

    def evaluate(self, context: SignalContext) -> ComponentSignal:
        prices = context.recent_prices
        if len(prices) < 61 and len(context.daily_bars) >= 61:
            prices = tuple(bar.close for bar in context.daily_bars)
        if len(prices) < 61:
            return ComponentSignal(self.name, Decimal("0"), True, "Moving average history unavailable")
        ma5 = sma(prices, 5)
        ma20 = sma(prices, 20)
        ma60 = sma(prices, 60)
        prev_ma20 = sum(prices[-21:-1]) / Decimal("20")
        score = Decimal("0")
        if ma5 > ma20 > ma60:
            score += Decimal("65")
        elif ma5 < ma20 < ma60:
            score -= Decimal("65")
        else:
            score += Decimal("20") if ma5 > ma20 else Decimal("-20")
        score += pct_change(ma20, prev_ma20) * Decimal("200")
        return ComponentSignal(
            self.name,
            clamp_score(score),
            True,
            f"MA5 {ma5:.2f}, MA20 {ma20:.2f}, MA60 {ma60:.2f}",
        )
