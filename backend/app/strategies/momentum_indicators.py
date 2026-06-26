from decimal import Decimal

from app.strategies.base import ComponentSignal, SignalComponent, SignalContext
from app.strategies.technical import clamp_score, macd_histogram, rsi


class MomentumIndicatorsStrategy(SignalComponent):
    name = "momentum_indicators"

    def evaluate(self, context: SignalContext) -> ComponentSignal:
        prices = context.recent_prices
        if len(prices) < 35 and len(context.daily_bars) >= 35:
            prices = tuple(bar.close for bar in context.daily_bars)
        current_rsi = rsi(prices, 14)
        previous_rsi = rsi(prices[:-1], 14) if len(prices) > 15 else None
        histogram = macd_histogram(prices)
        if current_rsi is None or previous_rsi is None or len(histogram) < 2:
            return ComponentSignal(self.name, Decimal("0"), True, "Momentum indicator history unavailable")
        rsi_slope = current_rsi - previous_rsi
        macd_slope = histogram[-1] - histogram[-2]
        score = Decimal("0")
        score += (current_rsi - Decimal("50")) * Decimal("1.2")
        score += rsi_slope * Decimal("4")
        score += Decimal("35") if histogram[-1] > 0 else Decimal("-35")
        score += Decimal("25") if macd_slope > 0 else Decimal("-25")
        if current_rsi > Decimal("78"):
            score -= (current_rsi - Decimal("78")) * Decimal("3")
        return ComponentSignal(
            self.name,
            clamp_score(score),
            True,
            f"RSI {current_rsi:.2f} ({rsi_slope:+.2f}), MACD histogram {histogram[-1]:.2f}",
        )
