from datetime import datetime
from decimal import Decimal
import httpx
from sqlalchemy.exc import IntegrityError

from app.config import Settings, TradingMode
from app.db.models import OrderRecord
from app.db.repository import TradingRepository
from app.kis.client import KISAPIError, KISConfigurationError
from app.kis.order import KISOrderService
from app.notifications.base import Notifier
from app.schemas.order import CancelOrderResponse, ManualOrderRequest, OrderResponse
from app.trading.order_manager import OrderManager
from app.trading.order_state import OrderState
from app.trading.risk_manager import OrderIntent, RiskContext, RiskManager


class IdempotencyConflict(ValueError):
    pass


class ExecutionEngine:
    """모든 주문을 영속화하고 리스크 검사 후 SIM 또는 KIS PAPER로 전송한다."""

    def __init__(
        self,
        settings: Settings,
        risk_manager: RiskManager,
        order_manager: OrderManager,
        notifier: Notifier,
        paper_order_service: KISOrderService | None = None,
    ) -> None:
        self.settings = settings
        self.risk_manager = risk_manager
        self.order_manager = order_manager
        self.notifier = notifier
        self.paper_order_service = paper_order_service
        paper = settings.trading_mode == TradingMode.PAPER
        self.context = RiskContext(
            api_connected=not paper,
            websocket_connected=not paper,
            account_synchronized=not paper,
            orders_synchronized=not paper,
        )
        self.automation_desired = False
        self.automation_enabled = False

    async def submit_manual(
        self,
        request: ManualOrderRequest,
        repository: TradingRepository,
        idempotency_key: str,
        *,
        source: str = "MANUAL",
        strategy_name: str | None = None,
        parent_order_id: str | None = None,
        reprice_count: int = 0,
    ) -> OrderResponse:
        existing = await repository.get_order_by_client_id(idempotency_key)
        if existing is not None:
            if not self._same_order(existing, request):
                raise IdempotencyConflict("Idempotency key was already used for a different order")
            return self._response(existing)

        order_id, _ = self.order_manager.create()
        record = OrderRecord(
            id=order_id,
            client_order_id=idempotency_key,
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            price=request.price,
            mode=self.settings.trading_mode,
            state=OrderState.SIGNAL,
            source=source,
            strategy_name=strategy_name,
            parent_order_id=parent_order_id,
            reprice_count=reprice_count,
            reference_cost_price=(
                self.context.position_average_prices.get(request.symbol)
                if request.side == "SELL"
                else None
            ),
            message="Order created",
        )
        try:
            await repository.add_order(record)
        except IntegrityError:
            await repository.session.rollback()
            existing = await repository.get_order_by_client_id(idempotency_key)
            if existing is not None and self._same_order(existing, request):
                return self._response(existing)
            raise IdempotencyConflict("Idempotency key was concurrently used for another order")
        intent = OrderIntent(
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            price=Decimal(request.price),
        )
        if (
            self.settings.trading_mode == TradingMode.PAPER
            and self.paper_order_service is not None
            and intent.side.upper() == "BUY"
        ):
            try:
                self.context.available_cash = await self.paper_order_service.get_orderable_cash(intent)
            except (KISAPIError, KISConfigurationError, httpx.HTTPError) as error:
                self.order_manager.transition(order_id, OrderState.REJECTED)
                await repository.update_order(
                    record,
                    state=OrderState.REJECTED,
                    rejection_code="ORDERABLE_CASH_UNAVAILABLE",
                    message=str(error),
                )
                return self._response(record)
        decision = self.risk_manager.evaluate(intent, self.context)
        if not decision.approved:
            self.order_manager.transition(order_id, OrderState.REJECTED)
            await repository.update_order(
                record,
                state=OrderState.REJECTED,
                rejection_code=decision.reasons[0],
                message="RiskManager blocked the order",
            )
            await repository.add_event(
                "RISK_BLOCK",
                record.message,
                {"order_id": order_id, "reasons": decision.reasons},
                level="BLOCK",
            )
            await self.notifier.send("RISK_BLOCK", f"{request.symbol}: {', '.join(decision.reasons)}")
            response = self._response(record)
            response.risk_reasons = list(decision.reasons)
            return response

        self.order_manager.transition(order_id, OrderState.RISK_CHECKED)
        await repository.update_order(record, state=OrderState.RISK_CHECKED)
        self.order_manager.transition(order_id, OrderState.ORDER_REQUESTED)
        await repository.update_order(record, state=OrderState.ORDER_REQUESTED)

        if self.settings.trading_mode == TradingMode.SIM:
            self.order_manager.transition(order_id, OrderState.ORDER_SENT)
            await repository.update_order(
                record,
                state=OrderState.ORDER_SENT,
                message="Simulated order accepted; no broker request was made",
            )
            self._register_pending(intent)
            await self.notifier.send("ORDER_SENT", f"{request.symbol} {request.side} SIM order")
            return self._response(record)

        if self.settings.trading_mode == TradingMode.LIVE:
            self.order_manager.transition(order_id, OrderState.REJECTED)
            await repository.update_order(
                record,
                state=OrderState.REJECTED,
                rejection_code="LIVE_NOT_IMPLEMENTED",
                message="LIVE order routing is intentionally unavailable",
            )
            return self._response(record)

        if self.paper_order_service is None:
            self.order_manager.transition(order_id, OrderState.ERROR)
            await repository.update_order(
                record,
                state=OrderState.ERROR,
                rejection_code="PAPER_SERVICE_NOT_READY",
                message="KIS PAPER order service is not configured",
            )
            return self._response(record)

        try:
            result = await self.paper_order_service.place_order(intent)
        except (httpx.TimeoutException, httpx.TransportError) as error:
            self.order_manager.transition(order_id, OrderState.RECONCILING)
            await repository.update_order(
                record,
                state=OrderState.RECONCILING,
                message="Broker submission result is unknown; reconciliation required",
            )
            await repository.add_event(
                "ORDER_UNKNOWN", str(error), {"order_id": order_id}, level="WARN"
            )
            return self._response(record)
        except (KISAPIError, KISConfigurationError) as error:
            self.order_manager.transition(order_id, OrderState.REJECTED)
            await repository.update_order(
                record,
                state=OrderState.REJECTED,
                rejection_code=getattr(error, "code", "KIS_ORDER_ERROR"),
                message=str(error),
            )
            return self._response(record)

        self.order_manager.transition(order_id, OrderState.ORDER_SENT)
        await repository.update_order(
            record,
            state=OrderState.ORDER_SENT,
            broker_order_id=result.broker_order_id,
            broker_org_no=result.broker_org_no,
            broker_order_date=datetime.now().strftime("%Y%m%d"),
            message=result.message,
        )
        self._register_pending(intent)
        await repository.add_event(
            "ORDER_SENT",
            result.message,
            {"order_id": order_id, "broker_order_id": result.broker_order_id},
        )
        await self.notifier.send("ORDER_SENT", result.message)
        return self._response(record)

    async def cancel_order(
        self, order_id: str, repository: TradingRepository
    ) -> CancelOrderResponse:
        record = await repository.get_order(order_id)
        if record is None:
            raise KeyError(order_id)
        if record.state not in {
            OrderState.ORDER_SENT,
            OrderState.PARTIALLY_FILLED,
            OrderState.RECONCILING,
        }:
            raise ValueError(f"Order in {record.state} state cannot be canceled")
        remaining = max(record.quantity - record.filled_quantity, 0)
        if self.settings.trading_mode == TradingMode.SIM:
            await repository.update_order(record, state=OrderState.CANCELED, message="SIM order canceled")
            self.context.active_order_keys.discard(f"{record.symbol}:{record.side}")
            if record.side == "BUY":
                self.context.pending_symbols.discard(record.symbol)
            else:
                self.context.pending_sell_quantities[record.symbol] = max(
                    self.context.pending_sell_quantities.get(record.symbol, 0) - remaining, 0
                )
            return CancelOrderResponse(order_id=order_id, state=OrderState.CANCELED, message=record.message)
        if self.paper_order_service is None or not record.broker_order_id or not record.broker_org_no:
            raise ValueError("Broker order identity is not available; reconcile before cancellation")
        await repository.update_order(record, state=OrderState.CANCEL_REQUESTED)
        try:
            result = await self.paper_order_service.cancel_order(
                broker_order_id=record.broker_order_id,
                broker_org_no=record.broker_org_no,
                quantity=remaining,
            )
        except (httpx.TimeoutException, httpx.TransportError):
            await repository.update_order(
                record,
                state=OrderState.RECONCILING,
                message="Cancellation result is unknown; reconciliation required",
            )
            return CancelOrderResponse(order_id=order_id, state=OrderState.RECONCILING, message=record.message)
        await repository.update_order(record, message=result.message)
        return CancelOrderResponse(order_id=order_id, state=OrderState.CANCEL_REQUESTED, message=result.message)

    async def set_emergency_stop(
        self, stopped: bool, repository: TradingRepository | None = None
    ) -> None:
        self.context.emergency_stopped = stopped
        if repository is not None:
            await repository.set_runtime_state("emergency_stopped", "true" if stopped else "false")
        if stopped:
            self.automation_enabled = False
            await self.notifier.send("AUTOMATION_STOPPED", "Emergency stop activated")

    def refresh_effective_automation(self, strategy_ready: bool) -> bool:
        self.automation_enabled = bool(
            self.automation_desired
            and not self.context.emergency_stopped
            and self.context.api_connected
            and self.context.websocket_connected
            and self.context.account_synchronized
            and self.context.orders_synchronized
            and strategy_ready
        )
        return self.automation_enabled

    def _register_pending(self, intent: OrderIntent) -> None:
        self.context.daily_order_count += 1
        self.context.pending_symbols.add(intent.symbol)
        self.context.active_order_keys.add(f"{intent.symbol}:{intent.side.upper()}")
        if intent.side.upper() == "SELL":
            self.context.pending_sell_quantities[intent.symbol] = (
                self.context.pending_sell_quantities.get(intent.symbol, 0) + intent.quantity
            )

    @staticmethod
    def _same_order(record: OrderRecord, request: ManualOrderRequest) -> bool:
        return bool(
            record.symbol == request.symbol
            and record.side == request.side
            and record.quantity == request.quantity
            and Decimal(record.price) == Decimal(request.price)
        )

    @staticmethod
    def _response(record: OrderRecord) -> OrderResponse:
        return OrderResponse(
            order_id=record.id,
            mode=record.mode,
            state=record.state,
            message=record.message,
            broker_order_id=record.broker_order_id,
            filled_quantity=record.filled_quantity,
            average_fill_price=record.average_fill_price,
            risk_reasons=[record.rejection_code] if record.rejection_code else [],
        )
