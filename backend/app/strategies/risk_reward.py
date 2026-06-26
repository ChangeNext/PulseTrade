from decimal import Decimal

from app.strategies.base import ComponentSignal, SignalComponent, SignalContext
from app.strategies.technical import clamp_score, merged_bars, pct_change, support_resistance


class RiskRewardStrategy(SignalComponent):
    name = "risk_reward"

    def evaluate(self, context: SignalContext) -> ComponentSignal:
        price = context.market.price
        bars = merged_bars(context.daily_bars, context.intraday_bars)
        if price <= 0 or len(bars) < 10:
            return ComponentSignal(self.name, Decimal("0"), True, "Risk/reward history unavailable")
        support, resistance = support_resistance(bars, price)
        if support is None or resistance is None:
            return ComponentSignal(self.name, Decimal("0"), True, "Risk/reward line is incomplete")
        risk_pct = pct_change(price, support)
        reward_pct = pct_change(resistance, price)
        if risk_pct <= 0:
            return ComponentSignal(self.name, Decimal("-80"), True, "Price is below support")
        ratio = reward_pct / risk_pct
        score = (ratio - Decimal("1")) * Decimal("60")
        if risk_pct > Decimal("2.5"):
            score -= (risk_pct - Decimal("2.5")) * Decimal("20")
        return ComponentSignal(
            self.name,
            clamp_score(score),
            True,
            f"Risk {risk_pct:.2f}%, reward {reward_pct:.2f}%, ratio {ratio:.2f}",
        )
