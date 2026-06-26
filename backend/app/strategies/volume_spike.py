from decimal import Decimal

from app.strategies.base import ComponentSignal, SignalComponent, SignalContext


class VolumeSpikeStrategy(SignalComponent):
    name = "volume_spike"

    def __init__(self, target_multiplier: Decimal = Decimal("2")) -> None:
        self.target_multiplier = target_multiplier

    def evaluate(self, context: SignalContext) -> ComponentSignal:
        average = context.market.average_volume
        if average <= 0:
            return ComponentSignal(self.name, Decimal("0"), True, "Average volume unavailable")
        ratio = Decimal(context.market.current_volume) / average
        score = max(Decimal("-100"), min(Decimal("100"), (ratio - Decimal("1")) * Decimal("100")))
        return ComponentSignal(
            self.name,
            score,
            True,
            f"1-minute volume is {ratio:.2f}x average (target {self.target_multiplier}x)",
        )
