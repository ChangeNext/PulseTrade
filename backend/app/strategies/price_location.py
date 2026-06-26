from decimal import Decimal

from app.strategies.base import ComponentSignal, SignalComponent, SignalContext
from app.strategies.technical import clamp_score, merged_bars, pct_change, support_resistance


class PriceLocationStrategy(SignalComponent):
    name = "price_location"

    def evaluate(self, context: SignalContext) -> ComponentSignal:
        price = context.market.price
        bars = merged_bars(context.daily_bars, context.intraday_bars)
        if price <= 0 or len(bars) < 10:
            return ComponentSignal(self.name, Decimal("0"), True, "Price location history unavailable")
        support, resistance = support_resistance(bars, price)
        if support is None and resistance is None:
            return ComponentSignal(self.name, Decimal("0"), True, "No nearby support/resistance")
        support_distance = pct_change(price, support) if support else Decimal("99")
        resistance_distance = pct_change(resistance, price) if resistance else Decimal("99")
        score = Decimal("0")
        if support is not None:
            score += max(Decimal("0"), Decimal("45") - support_distance * Decimal("20"))
        if resistance is not None and resistance_distance < Decimal("1.2"):
            score -= (Decimal("1.2") - resistance_distance) * Decimal("45")
        if support_distance > Decimal("4") and resistance_distance < Decimal("2"):
            score -= Decimal("35")
        return ComponentSignal(
            self.name,
            clamp_score(score),
            True,
            f"Support {support or '-'} ({support_distance:.2f}%), resistance {resistance or '-'} ({resistance_distance:.2f}%)",
        )
