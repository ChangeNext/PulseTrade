import asyncio
from datetime import datetime, timezone

from app.config import Settings
from app.db.repository import TradingRepository
from app.schemas.order import ManualOrderRequest
from app.strategies.base import OrderBookSnapshot
from app.trading.execution_engine import ExecutionEngine
from app.trading.order_state import OrderState


class OrderSupervisor:
    def __init__(self, settings: Settings, engine: ExecutionEngine) -> None:
        self.settings = settings
        self.engine = engine
        self._lock = asyncio.Lock()

    async def sweep(
        self,
        symbol: str,
        book: OrderBookSnapshot,
        repository: TradingRepository,
    ) -> None:
        if self._lock.locked():
            return
        async with self._lock:
            for order in await repository.strategy_orders_for_supervision():
                if order.symbol != symbol:
                    continue
                if order.state == OrderState.CANCELED and order.auto_reprice_requested:
                    await self._replace(order, book, repository)
                    continue
                if order.auto_reprice_requested:
                    continue
                if order.state not in {OrderState.ORDER_SENT, OrderState.PARTIALLY_FILLED}:
                    continue
                created = order.created_at
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                age = (datetime.now(timezone.utc) - created).total_seconds()
                if age < self.settings.strategy_order_ttl_seconds:
                    continue
                if order.reprice_count >= self.settings.strategy_max_reprices:
                    await self.engine.cancel_order(order.id, repository)
                    await repository.add_event(
                        "REPRICE_EXHAUSTED",
                        f"{order.symbol} exceeded reprice limit",
                        {"order_id": order.id, "source": order.source},
                        level="ERROR",
                    )
                    if order.source == "EXIT":
                        await self.engine.set_emergency_stop(True, repository)
                    continue
                await repository.set_auto_reprice_requested(order, True)
                await self.engine.cancel_order(order.id, repository)
                if order.state == OrderState.CANCELED:
                    await self._replace(order, book, repository)

    async def _replace(
        self, order, book: OrderBookSnapshot, repository: TradingRepository
    ) -> None:
        remaining = max(order.quantity - order.filled_quantity, 0)
        if remaining <= 0:
            await repository.set_auto_reprice_requested(order, False)
            return
        price = book.best_ask if order.side == "BUY" else book.best_bid
        if price <= 0:
            return
        root_id = order.parent_order_id or order.id
        attempt = order.reprice_count + 1
        response = await self.engine.submit_manual(
            ManualOrderRequest(
                symbol=order.symbol,
                side=order.side,
                quantity=remaining,
                price=price,
            ),
            repository,
            f"reprice:{root_id}:{attempt}",
            source=order.source,
            strategy_name=order.strategy_name,
            parent_order_id=root_id,
            reprice_count=attempt,
        )
        await repository.set_auto_reprice_requested(order, False)
        if response.state in {OrderState.ORDER_SENT, OrderState.RECONCILING}:
            await repository.replace_strategy_order_reference(
                order.id, response.order_id, order.source
            )
            await repository.add_event(
                "ORDER_REPRICED",
                f"{order.symbol} repriced to {price}",
                {"old_order_id": order.id, "new_order_id": response.order_id, "attempt": attempt},
            )
