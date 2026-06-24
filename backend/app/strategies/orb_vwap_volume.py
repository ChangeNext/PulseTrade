from decimal import Decimal

from app.strategies.base import MarketSnapshot, Strategy, StrategySignal


class OrbVwapVolumeStrategy(Strategy):
    """주문을 실행하지 않고 조건 충족 시 SIGNAL만 생성한다."""

    name = "ORB_VWAP_VOLUME"

    def __init__(self, volume_multiplier: Decimal = Decimal("2")) -> None:
        self.volume_multiplier = volume_multiplier

    def evaluate(self, snapshot: MarketSnapshot) -> StrategySignal | None:
        if snapshot.already_held or snapshot.has_pending_order:
            return None
        if snapshot.average_volume <= 0:
            return None
        if snapshot.price <= snapshot.opening_range_high:
            return None
        if snapshot.price <= snapshot.vwap:
            return None
        if Decimal(snapshot.current_volume) <= snapshot.average_volume * self.volume_multiplier:
            return None
        return StrategySignal(
            strategy=self.name,
            symbol=snapshot.symbol,
            action="BUY",
            reason="Opening range breakout above VWAP with volume surge",
        )

