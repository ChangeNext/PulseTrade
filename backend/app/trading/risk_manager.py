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
    position_quantities: dict[str, int] = field(default_factory=dict)
    position_average_prices: dict[str, Decimal] = field(default_factory=dict)
    position_current_prices: dict[str, Decimal] = field(default_factory=dict)
    pending_sell_quantities: dict[str, int] = field(default_factory=dict)
    available_cash: Decimal | None = None
    pending_symbols: set[str] = field(default_factory=set)
    active_order_keys: set[str] = field(default_factory=set)
    api_connected: bool = True
    websocket_connected: bool = True
    emergency_stopped: bool = False
    account_synchronized: bool = True
    orders_synchronized: bool = True
    market_open: bool = True
    pnl_synchronized: bool = True


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
        if not context.account_synchronized or not context.orders_synchronized:
            reasons.append("BROKER_STATE_NOT_SYNCHRONIZED")
        if side == "BUY" and not context.pnl_synchronized:
            reasons.append("DAILY_PNL_NOT_SYNCHRONIZED")
        if not context.market_open:
            reasons.append("MARKET_CLOSED")
        if intent.quantity <= 0 or intent.price <= 0:
            reasons.append("INVALID_ORDER_VALUE")
        if intent.price > 0 and intent.price % self._tick_size(intent.price) != 0:
            reasons.append("INVALID_TICK_SIZE")
        if side == "BUY" and intent.amount > self.max_order_amount:
            reasons.append("MAX_ORDER_AMOUNT_EXCEEDED")
        if side == "BUY" and context.daily_realized_pnl <= -self.max_daily_loss:
            reasons.append("MAX_DAILY_LOSS_REACHED")
        if side == "BUY" and context.daily_order_count >= self.max_daily_orders:
            reasons.append("MAX_DAILY_ORDERS_REACHED")
        if order_key in context.active_order_keys:
            reasons.append("DUPLICATE_ORDER")
        if side == "BUY" and intent.symbol in context.pending_symbols:
            reasons.append("PENDING_ORDER_EXISTS")
        if side == "BUY" and context.available_cash is not None and intent.amount > context.available_cash:
            reasons.append("INSUFFICIENT_ORDERABLE_CASH")
        if side == "SELL":
            sellable = context.position_quantities.get(intent.symbol, 0) - context.pending_sell_quantities.get(
                intent.symbol, 0
            )
            if intent.quantity > sellable:
                reasons.append("INSUFFICIENT_POSITION_QUANTITY")
        projected = context.position_amounts.get(intent.symbol, Decimal("0"))
        if side == "BUY":
            projected += intent.amount
        if projected > self.max_position_amount:
            reasons.append("MAX_POSITION_AMOUNT_EXCEEDED")

        return RiskDecision(approved=not reasons, reasons=tuple(reasons))

    @staticmethod
    def _tick_size(price: Decimal) -> Decimal:
        if price < 2_000:
            return Decimal("1")
        if price < 5_000:
            return Decimal("5")
        if price < 20_000:
            return Decimal("10")
        if price < 50_000:
            return Decimal("50")
        if price < 200_000:
            return Decimal("100")
        if price < 500_000:
            return Decimal("500")
        return Decimal("1000")
