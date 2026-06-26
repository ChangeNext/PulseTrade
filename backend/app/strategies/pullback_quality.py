from decimal import Decimal

from app.strategies.base import ComponentSignal, SignalComponent, SignalContext
from app.strategies.technical import average, clamp_score, pct_change, sma


class PullbackQualityStrategy(SignalComponent):
    name = "pullback_quality"

    def evaluate(self, context: SignalContext) -> ComponentSignal:
        bars = context.intraday_bars
        prices = context.recent_prices
        if len(bars) < 25 or len(prices) < 21:
            return ComponentSignal(self.name, Decimal("0"), True, "Pullback history unavailable")
        recent = bars[-25:]
        peak_index, peak = max(enumerate(recent), key=lambda item: item[1].high)
        after_peak = recent[peak_index + 1 :]
        if len(after_peak) < 3:
            return ComponentSignal(self.name, Decimal("0"), True, "No clear pullback after recent high")
        pullback_low = min(bar.low for bar in after_peak)
        pullback_depth = abs(pct_change(pullback_low, peak.high))
        pullback_volume = average([Decimal(bar.volume) for bar in after_peak])
        prior_volume = average([Decimal(bar.volume) for bar in recent[: max(1, peak_index + 1)]])
        ma20 = sma(prices, 20)
        last = bars[-1]
        score = Decimal("0")
        if last.close > ma20 and pullback_volume < prior_volume:
            score += Decimal("45")
        if last.close > after_peak[-2].close and last.volume > after_peak[-2].volume:
            score += Decimal("25")
        if pullback_depth > Decimal("3"):
            score -= (pullback_depth - Decimal("3")) * Decimal("18")
        if pullback_volume > prior_volume * Decimal("1.3"):
            score -= Decimal("35")
        return ComponentSignal(
            self.name,
            clamp_score(score),
            True,
            f"Pullback {pullback_depth:.2f}%, volume {pullback_volume:.0f}/{prior_volume:.0f}",
        )
