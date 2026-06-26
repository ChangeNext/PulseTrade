from decimal import Decimal

from app.strategies.base import ComponentSignal, SignalComponent, SignalContext
from app.strategies.technical import clamp_score


class CandleQualityStrategy(SignalComponent):
    name = "candle_quality"

    def evaluate(self, context: SignalContext) -> ComponentSignal:
        if not context.intraday_bars:
            return ComponentSignal(self.name, Decimal("0"), True, "Candle history unavailable")
        bar = context.intraday_bars[-1]
        if bar.open <= 0 or bar.high <= bar.low:
            return ComponentSignal(self.name, Decimal("0"), True, "Candle baseline is invalid")
        candle_range = bar.high - bar.low
        body = abs(bar.close - bar.open)
        upper_wick = bar.high - max(bar.open, bar.close)
        lower_wick = min(bar.open, bar.close) - bar.low
        body_ratio = body / candle_range
        upper_ratio = upper_wick / candle_range
        lower_ratio = lower_wick / candle_range
        score = body_ratio * Decimal("60")
        score += Decimal("25") if bar.close > bar.open else Decimal("-25")
        score += lower_ratio * Decimal("35")
        score -= upper_ratio * Decimal("55")
        return ComponentSignal(
            self.name,
            clamp_score(score),
            True,
            f"Body {body_ratio:.2f}, upper wick {upper_ratio:.2f}, lower wick {lower_ratio:.2f}",
        )
