from decimal import Decimal

from app.strategies.base import ComponentSignal, SignalComponent, SignalContext
from app.strategies.technical import clamp_score


class TrendStructureStrategy(SignalComponent):
    name = "trend_structure"

    def evaluate(self, context: SignalContext) -> ComponentSignal:
        bars = context.intraday_bars
        if len(bars) < 20:
            return ComponentSignal(self.name, Decimal("0"), True, "Trend structure history unavailable")
        previous = bars[-20:-10]
        current = bars[-10:]
        prev_high = max(bar.high for bar in previous)
        prev_low = min(bar.low for bar in previous)
        curr_high = max(bar.high for bar in current)
        curr_low = min(bar.low for bar in current)
        higher_high = curr_high > prev_high
        higher_low = curr_low > prev_low
        lower_high = curr_high < prev_high
        lower_low = curr_low < prev_low
        if higher_high and higher_low:
            score = Decimal("80")
        elif lower_high and lower_low:
            score = Decimal("-80")
        elif higher_low:
            score = Decimal("30")
        elif lower_high:
            score = Decimal("-30")
        else:
            score = Decimal("0")
        return ComponentSignal(
            self.name,
            clamp_score(score),
            True,
            f"High {prev_high}->{curr_high}, low {prev_low}->{curr_low}",
        )
