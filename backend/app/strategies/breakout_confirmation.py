from decimal import Decimal

from app.strategies.base import ComponentSignal, SignalComponent, SignalContext
from app.strategies.technical import clamp_score, pct_change, volume_average


class BreakoutConfirmationStrategy(SignalComponent):
    name = "breakout_confirmation"

    def evaluate(self, context: SignalContext) -> ComponentSignal:
        bars = context.intraday_bars
        if len(bars) < 21:
            return ComponentSignal(self.name, Decimal("0"), True, "Breakout history unavailable")
        current = bars[-1]
        previous = bars[-21:-1]
        prior_high = max(bar.high for bar in previous)
        average_volume = volume_average(previous, min(20, len(previous)))
        volume_ratio = Decimal(current.volume) / average_volume if average_volume > 0 else Decimal("0")
        close_break_pct = pct_change(current.close, prior_high)
        score = close_break_pct * Decimal("120") + (volume_ratio - Decimal("1")) * Decimal("35")
        if current.high > prior_high and current.close <= prior_high:
            score -= Decimal("55")
        return ComponentSignal(
            self.name,
            clamp_score(score),
            True,
            f"Close {close_break_pct:.2f}% from prior high, volume {volume_ratio:.2f}x",
        )
