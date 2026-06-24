from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from app.strategies.base import SignalContext


@dataclass(frozen=True)
class StrategyRiskDecision:
    can_enter: bool
    reason: str


class StrategyRiskFilter:
    """시장 신호 품질만 검사하며 계좌 리스크는 RiskManager가 최종 판단한다."""

    def __init__(
        self,
        *,
        max_spread_bps: Decimal = Decimal("20"),
        max_quote_age_seconds: Decimal = Decimal("2"),
    ) -> None:
        self.max_spread_bps = max_spread_bps
        self.max_quote_age_seconds = max_quote_age_seconds

    def evaluate(self, context: SignalContext) -> StrategyRiskDecision:
        if context.already_held:
            return StrategyRiskDecision(False, "Position already held")
        if context.has_pending_order:
            return StrategyRiskDecision(False, "Pending order exists")
        if context.orderbook is None or context.trade_strength is None:
            return StrategyRiskDecision(False, "Realtime order book/trade strength is not ready")
        if context.trading_halted:
            return StrategyRiskDecision(False, "Trading is halted")
        if context.vi_active:
            return StrategyRiskDecision(False, "Volatility interruption is active")
        book = context.orderbook
        if book.best_ask <= 0 or book.best_bid <= 0 or book.best_ask < book.best_bid:
            return StrategyRiskDecision(False, "Order book prices are invalid")
        midpoint = (book.best_ask + book.best_bid) / Decimal("2")
        spread_bps = (book.best_ask - book.best_bid) / midpoint * Decimal("10000")
        if spread_bps > self.max_spread_bps:
            return StrategyRiskDecision(False, f"Spread {spread_bps:.2f}bps exceeds limit")
        if book.received_at is None:
            return StrategyRiskDecision(False, "Order book timestamp is unavailable")
        age = Decimal(str((datetime.now(timezone.utc) - book.received_at).total_seconds()))
        if age > self.max_quote_age_seconds:
            return StrategyRiskDecision(False, f"Order book is stale ({age:.2f}s)")
        return StrategyRiskDecision(True, "Strategy market-data checks passed")
