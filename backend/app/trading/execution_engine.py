from decimal import Decimal

from app.config import Settings, TradingMode
from app.kis.order import KISOrderService
from app.notifications.base import Notifier
from app.schemas.order import ManualOrderRequest, OrderResponse
from app.trading.order_manager import OrderManager
from app.trading.order_state import OrderState
from app.trading.risk_manager import OrderIntent, RiskContext, RiskManager


class ExecutionEngine:
    """신호/수동 주문을 리스크 검사 후 SIM 또는 명시적으로 해제된 LIVE로 보낸다."""

    def __init__(
        self,
        settings: Settings,
        risk_manager: RiskManager,
        order_manager: OrderManager,
        notifier: Notifier,
        live_order_service: KISOrderService | None = None,
    ) -> None:
        self.settings = settings
        self.risk_manager = risk_manager
        self.order_manager = order_manager
        self.notifier = notifier
        self.live_order_service = live_order_service
        self.context = RiskContext()
        self.automation_enabled = False

    async def submit_manual(self, request: ManualOrderRequest) -> OrderResponse:
        order_id, _ = self.order_manager.create()
        intent = OrderIntent(
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            price=Decimal(request.price),
        )
        decision = self.risk_manager.evaluate(intent, self.context)
        if not decision.approved:
            self.order_manager.transition(order_id, OrderState.REJECTED)
            await self.notifier.send("RISK_BLOCK", f"{request.symbol}: {', '.join(decision.reasons)}")
            return OrderResponse(
                order_id=order_id,
                mode=self.settings.trading_mode,
                state=OrderState.REJECTED,
                message="RiskManager blocked the order",
                risk_reasons=list(decision.reasons),
            )

        self.order_manager.transition(order_id, OrderState.RISK_CHECKED)
        self.order_manager.transition(order_id, OrderState.ORDER_REQUESTED)

        if self.settings.trading_mode in {TradingMode.SIM, TradingMode.PAPER}:
            self.order_manager.transition(order_id, OrderState.ORDER_SENT)
            self.context.daily_order_count += 1
            self.context.pending_symbols.add(intent.symbol)
            self.context.active_order_keys.add(f"{intent.symbol}:{intent.side.upper()}")
            await self.notifier.send("ORDER_SENT", f"{request.symbol} {request.side} SIM order")
            return OrderResponse(
                order_id=order_id,
                mode=self.settings.trading_mode,
                state=OrderState.ORDER_SENT,
                message="Simulated order accepted; no broker request was made",
            )

        if not self.settings.enable_live_trading:
            self.order_manager.transition(order_id, OrderState.REJECTED)
            return OrderResponse(
                order_id=order_id,
                mode=self.settings.trading_mode,
                state=OrderState.REJECTED,
                message="LIVE trading is disabled by configuration",
            )
        if request.live_confirmation != self.settings.live_confirmation_phrase:
            self.order_manager.transition(order_id, OrderState.REJECTED)
            return OrderResponse(
                order_id=order_id,
                mode=self.settings.trading_mode,
                state=OrderState.REJECTED,
                message="Explicit LIVE confirmation phrase is required",
            )
        if self.live_order_service is None:
            self.order_manager.transition(order_id, OrderState.ERROR)
            return OrderResponse(
                order_id=order_id,
                mode=self.settings.trading_mode,
                state=OrderState.ERROR,
                message="KIS live order service is not configured",
            )

        result = await self.live_order_service.place_order(intent)
        next_state = OrderState.ORDER_SENT if result.accepted else OrderState.REJECTED
        self.order_manager.transition(order_id, next_state)
        if result.accepted:
            self.context.daily_order_count += 1
            self.context.pending_symbols.add(intent.symbol)
            self.context.active_order_keys.add(f"{intent.symbol}:{intent.side.upper()}")
        await self.notifier.send("ORDER_SENT" if result.accepted else "ORDER_REJECTED", result.message)
        return OrderResponse(
            order_id=order_id,
            mode=self.settings.trading_mode,
            state=next_state,
            message=result.message,
        )

    async def set_emergency_stop(self, stopped: bool) -> None:
        self.context.emergency_stopped = stopped
        if stopped:
            self.automation_enabled = False
            await self.notifier.send("AUTOMATION_STOPPED", "Emergency stop activated")
