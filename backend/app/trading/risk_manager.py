from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True)
class OrderIntent:
    symbol: str
    side: str
    quantity: int
    price: Decimal

    @property
    def amount(self) -> Decimal:
        return self.price * self.quantity


@dataclass
class RiskContext:
    daily_realized_pnl: Decimal = Decimal("0")
    daily_order_count: int = 0
    position_amounts: dict[str, Decimal] = field(default_factory=dict)
    pending_symbols: set[str] = field(default_factory=set)
    active_order_keys: set[str] = field(default_factory=set)
    api_connected: bool = True
    websocket_connected: bool = True
    emergency_stopped: bool = False


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    reasons: tuple[str, ...] = ()


class RiskManager:
    """주문 전 모든 안전 정책을 한곳에서 평가한다."""

    def __init__(
        self,
        max_order_amount: Decimal = Decimal("100000"),
        max_daily_loss: Decimal = Decimal("50000"),
        max_daily_orders: int = 5,
        max_position_amount: Decimal = Decimal("300000"),
    ) -> None:
        self.max_order_amount = max_order_amount
        self.max_daily_loss = max_daily_loss
        self.max_daily_orders = max_daily_orders
        self.max_position_amount = max_position_amount

    def evaluate(self, intent: OrderIntent, context: RiskContext) -> RiskDecision:
        reasons: list[str] = []
        side = intent.side.upper()
        order_key = f"{intent.symbol}:{side}"

        if context.emergency_stopped:
            reasons.append("EMERGENCY_STOPPED")
        if not context.api_connected:
            reasons.append("API_DISCONNECTED")
        if not context.websocket_connected:
            reasons.append("WEBSOCKET_DISCONNECTED")
        if intent.quantity <= 0 or intent.price <= 0:
            reasons.append("INVALID_ORDER_VALUE")
        if intent.amount > self.max_order_amount:
            reasons.append("MAX_ORDER_AMOUNT_EXCEEDED")
        if context.daily_realized_pnl <= -self.max_daily_loss:
            reasons.append("MAX_DAILY_LOSS_REACHED")
        if context.daily_order_count >= self.max_daily_orders:
            reasons.append("MAX_DAILY_ORDERS_REACHED")
        if order_key in context.active_order_keys:
            reasons.append("DUPLICATE_ORDER")
        if side == "BUY" and intent.symbol in context.pending_symbols:
            reasons.append("PENDING_ORDER_EXISTS")
        projected = context.position_amounts.get(intent.symbol, Decimal("0"))
        if side == "BUY":
            projected += intent.amount
        if projected > self.max_position_amount:
            reasons.append("MAX_POSITION_AMOUNT_EXCEEDED")

        return RiskDecision(approved=not reasons, reasons=tuple(reasons))

