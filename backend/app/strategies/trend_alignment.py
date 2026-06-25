from decimal import Decimal

from app.strategies.base import ComponentSignal, SignalComponent, SignalContext


class TrendAlignmentStrategy(SignalComponent):
    name = "trend_alignment"

    def __init__(self, short_window: int = 5, long_window: int = 20) -> None:
        self.short_window = short_window
        self.long_window = long_window

    def evaluate(self, context: SignalContext) -> ComponentSignal:
        prices = context.recent_prices
        if len(prices) < self.long_window + 1:
            return ComponentSignal(self.name, Decimal("0"), False, "Trend history unavailable")
        short_prices = prices[-self.short_window :]
        long_prices = prices[-self.long_window :]
        previous_long_prices = prices[-self.long_window - 1 : -1]
        short_average = sum(short_prices) / Decimal(len(short_prices))
        long_average = sum(long_prices) / Decimal(len(long_prices))
        previous_long_average = sum(previous_long_prices) / Decimal(len(previous_long_prices))
        if long_average <= 0 or previous_long_average <= 0:
            return ComponentSignal(self.name, Decimal("0"), False, "Trend baseline is invalid")

        alignment_pct = (short_average - long_average) / long_average * Decimal("100")
        slope_pct = (long_average - previous_long_average) / previous_long_average * Decimal("100")
        extension_pct = (prices[-1] - long_average) / long_average * Decimal("100")
        score = (
            alignment_pct * Decimal("60")
            + slope_pct * Decimal("240")
            + extension_pct * Decimal("20")
        )
        if extension_pct > Decimal("3"):
            score -= (extension_pct - Decimal("3")) * Decimal("25")
        score = max(Decimal("-100"), min(Decimal("100"), score))
        return ComponentSignal(
            self.name,
            score,
            True,
            (
                f"MA{self.short_window}/MA{self.long_window} {alignment_pct:.3f}%, "
                f"MA{self.long_window} slope {slope_pct:.3f}%, extension {extension_pct:.3f}%"
            ),
        )
