from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from app.config import TradingMode
from app.db.models import OrderRecord
from app.db.repository import TradingRepository
from app.kis.account import KISAccountService
from app.kis.order import BrokerOrderSnapshot, KISOrderService
from app.kis.market import KISMarketService
from app.trading.execution_engine import ExecutionEngine


class ReconciliationService:
    def __init__(
        self,
        engine: ExecutionEngine,
        account_service: KISAccountService,
        order_service: KISOrderService,
        market_service: KISMarketService | None = None,
    ) -> None:
        self.engine = engine
        self.account_service = account_service
        self.order_service = order_service
        self.market_service = market_service
        self.last_error: str | None = None

    async def synchronize(self, repository: TradingRepository) -> dict:
        context = self.engine.context
        context.account_synchronized = False
        context.orders_synchronized = False
        try:
            balance = await self.account_service.synchronize()
            context.available_cash = balance.cash
            context.position_quantities = {row.symbol: row.quantity for row in balance.positions}
            context.position_average_prices = {
                row.symbol: row.average_price for row in balance.positions
            }
            context.position_amounts = {
                row.symbol: row.evaluation_amount for row in balance.positions
            }
            context.api_connected = True
            context.account_synchronized = True
            now = datetime.now(timezone(timedelta(hours=9)))
            trading_day = await self.market_service.is_trading_day() if self.market_service else now.weekday() < 5
            context.market_open = bool(trading_day and time(9, 0) <= now.time() <= time(15, 30))

            snapshots = await self.order_service.list_daily_orders()
            today = datetime.now(timezone(timedelta(hours=9))).strftime("%Y%m%d")
            await repository.expire_prior_day_orders(today)
            for snapshot in snapshots:
                await self._apply_snapshot(repository, snapshot)
            context.daily_realized_pnl, context.pnl_synchronized = (
                await repository.daily_realized_pnl(today)
            )
            context.daily_order_count = len(snapshots)
            active = await repository.active_orders()
            context.pending_symbols = {row.symbol for row in active if row.side == "BUY"}
            context.active_order_keys = {f"{row.symbol}:{row.side}" for row in active}
            context.pending_sell_quantities = {}
            for row in active:
                if row.side == "SELL":
                    context.pending_sell_quantities[row.symbol] = (
                        context.pending_sell_quantities.get(row.symbol, 0)
                        + max(row.quantity - row.filled_quantity, 0)
                    )
            context.orders_synchronized = True
            self.last_error = None
            return {
                "account_synced": True,
                "orders_synced": True,
                "positions": len(balance.positions),
                "orders": len(snapshots),
                "pnl_synced": context.pnl_synchronized,
            }
        except Exception as error:
            context.api_connected = False
            self.last_error = str(error)
            await repository.add_event("RECONCILE_ERROR", str(error), level="ERROR")
            raise

    async def _apply_snapshot(
        self, repository: TradingRepository, snapshot: BrokerOrderSnapshot
    ) -> None:
        record = await repository.get_order_by_broker_id(
            snapshot.broker_order_id, snapshot.order_date
        )
        if record is None:
            record = await repository.find_ambiguous_order(
                symbol=snapshot.symbol,
                side=snapshot.side,
                quantity=snapshot.quantity,
                price=snapshot.price,
            )
        if record is None:
            record = OrderRecord(
                id=str(uuid4()),
                client_order_id=f"broker:{snapshot.order_date}:{snapshot.broker_order_id}",
                broker_order_id=snapshot.broker_order_id,
                broker_order_date=snapshot.order_date,
                broker_org_no=snapshot.broker_org_no,
                symbol=snapshot.symbol,
                side=snapshot.side,
                quantity=snapshot.quantity,
                price=snapshot.price,
                mode=TradingMode.PAPER,
                state=snapshot.state,
                source="RECOVERY",
                message="Recovered from KIS",
            )
            await repository.add_order(record)
        previous_filled = record.filled_quantity
        previous_average = record.average_fill_price
        await repository.update_order(
            record,
            state=snapshot.state,
            broker_order_id=snapshot.broker_order_id,
            broker_order_date=snapshot.order_date,
            broker_org_no=snapshot.broker_org_no,
            filled_quantity=snapshot.filled_quantity,
            average_fill_price=snapshot.average_fill_price,
            message="Synchronized from KIS",
        )
        delta = snapshot.filled_quantity - previous_filled
        if delta > 0 and snapshot.average_fill_price is not None:
            incremental_price = snapshot.average_fill_price
            if previous_filled > 0 and previous_average is not None:
                incremental_price = (
                    snapshot.average_fill_price * snapshot.filled_quantity
                    - Decimal(previous_average) * previous_filled
                ) / delta
            await repository.add_fill_once(
                fill_key=f"{snapshot.broker_order_id}:{snapshot.filled_quantity}:{snapshot.average_fill_price}",
                order_id=record.id,
                quantity=delta,
                price=Decimal(incremental_price),
            )
        if snapshot.state == "FILLED" and record.source == "EXIT":
            await repository.close_strategy_entry_by_exit(record.id)
