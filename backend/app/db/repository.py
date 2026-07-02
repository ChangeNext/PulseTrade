import json
from datetime import date
from decimal import Decimal

from sqlalchemy import case, delete, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    EventLog,
    FillRecord,
    ListedStock,
    MarketBarRecord,
    OrderRecord,
    RuntimeState,
    StrategyEntry,
)
from app.stock_listing import ListedStock as ParsedListedStock


class TradingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_order(self, order: OrderRecord, *, commit: bool = True) -> OrderRecord:
        self.session.add(order)
        if commit:
            await self.session.commit()
            await self.session.refresh(order)
        return order

    async def get_order(self, order_id: str) -> OrderRecord | None:
        return await self.session.get(OrderRecord, order_id)

    async def get_order_by_client_id(self, client_order_id: str) -> OrderRecord | None:
        return await self.session.scalar(
            select(OrderRecord).where(OrderRecord.client_order_id == client_order_id)
        )

    async def get_order_by_broker_id(
        self, broker_order_id: str, broker_order_date: str | None = None
    ) -> OrderRecord | None:
        query = select(OrderRecord).where(OrderRecord.broker_order_id == broker_order_id)
        if broker_order_date is not None:
            query = query.where(OrderRecord.broker_order_date == broker_order_date)
        return await self.session.scalar(
            query.order_by(desc(OrderRecord.created_at))
        )

    async def find_ambiguous_order(
        self, *, symbol: str, side: str, quantity: int, price: Decimal
    ) -> OrderRecord | None:
        rows = list(
            await self.session.scalars(
                select(OrderRecord).where(
                    OrderRecord.state == "RECONCILING",
                    OrderRecord.broker_order_id.is_(None),
                    OrderRecord.symbol == symbol,
                    OrderRecord.side == side,
                    OrderRecord.quantity == quantity,
                    OrderRecord.price == price,
                )
            )
        )
        return rows[0] if len(rows) == 1 else None

    async def update_order(
        self,
        order: OrderRecord,
        *,
        state: str | None = None,
        broker_order_id: str | None = None,
        broker_org_no: str | None = None,
        broker_order_date: str | None = None,
        filled_quantity: int | None = None,
        average_fill_price: Decimal | None = None,
        rejection_code: str | None = None,
        message: str | None = None,
        commission: Decimal | None = None,
        tax: Decimal | None = None,
        commit: bool = True,
    ) -> OrderRecord:
        if state is not None:
            order.state = state
        if broker_order_id is not None:
            order.broker_order_id = broker_order_id
        if broker_org_no is not None:
            order.broker_org_no = broker_org_no
        if broker_order_date is not None:
            order.broker_order_date = broker_order_date
        if filled_quantity is not None:
            order.filled_quantity = filled_quantity
        if average_fill_price is not None:
            order.average_fill_price = average_fill_price
        if rejection_code is not None:
            order.rejection_code = rejection_code
        if message is not None:
            order.message = message
        if commission is not None:
            order.commission = commission
        if tax is not None:
            order.tax = tax
        if commit:
            await self.session.commit()
            await self.session.refresh(order)
        return order

    async def add_fill_once(
        self, *, fill_key: str, order_id: str, quantity: int, price: Decimal
    ) -> FillRecord | None:
        existing = await self.session.scalar(select(FillRecord).where(FillRecord.fill_key == fill_key))
        if existing is not None:
            return None
        fill = FillRecord(fill_key=fill_key, order_id=order_id, quantity=quantity, price=price)
        self.session.add(fill)
        await self.session.commit()
        return fill

    async def add_event(
        self,
        category: str,
        message: str,
        payload: dict | None = None,
        *,
        level: str = "INFO",
    ) -> None:
        self.session.add(
            EventLog(
                category=category,
                level=level,
                message=message,
                payload_json=json.dumps(payload or {}, ensure_ascii=False, default=str),
            )
        )
        await self.session.commit()

    async def recent_orders(self, limit: int = 100) -> list[OrderRecord]:
        result = await self.session.scalars(
            select(OrderRecord).order_by(desc(OrderRecord.created_at)).limit(limit)
        )
        return list(result)

    async def active_orders(self) -> list[OrderRecord]:
        terminal = {"FILLED", "CANCELED", "REJECTED", "ERROR"}
        result = await self.session.scalars(select(OrderRecord).where(OrderRecord.state.not_in(terminal)))
        return list(result)

    async def active_sim_orders(self, symbol: str | None = None) -> list[OrderRecord]:
        terminal = {"FILLED", "CANCELED", "REJECTED", "ERROR"}
        query = select(OrderRecord).where(
            OrderRecord.mode == "SIM", OrderRecord.state.not_in(terminal)
        )
        if symbol is not None:
            query = query.where(OrderRecord.symbol == symbol)
        result = await self.session.scalars(query.order_by(OrderRecord.created_at))
        return list(result)

    async def sim_orders(self) -> list[OrderRecord]:
        result = await self.session.scalars(
            select(OrderRecord).where(OrderRecord.mode == "SIM").order_by(OrderRecord.created_at)
        )
        return list(result)

    async def strategy_orders_for_supervision(self) -> list[OrderRecord]:
        result = await self.session.scalars(
            select(OrderRecord).where(
                OrderRecord.source.in_({"STRATEGY", "EXIT"}),
                OrderRecord.state.in_({"ORDER_SENT", "PARTIALLY_FILLED", "CANCELED"}),
            ).order_by(OrderRecord.created_at)
        )
        return list(result)

    async def set_auto_reprice_requested(self, order: OrderRecord, requested: bool) -> None:
        order.auto_reprice_requested = requested
        await self.session.commit()

    async def replace_strategy_order_reference(
        self, old_order_id: str, new_order_id: str, source: str
    ) -> None:
        if source == "EXIT":
            entry = await self.session.scalar(
                select(StrategyEntry).where(StrategyEntry.exit_order_id == old_order_id)
            )
            if entry is not None:
                entry.exit_order_id = new_order_id
        else:
            entry = await self.session.scalar(
                select(StrategyEntry).where(StrategyEntry.entry_order_id == old_order_id)
            )
            if entry is not None:
                entry.entry_order_id = new_order_id
        await self.session.commit()

    async def expire_prior_day_orders(self, broker_order_date: str) -> None:
        terminal = {"FILLED", "CANCELED", "REJECTED", "ERROR"}
        rows = list(
            await self.session.scalars(
                select(OrderRecord).where(
                    OrderRecord.state.not_in(terminal),
                    OrderRecord.broker_order_date.is_not(None),
                    OrderRecord.broker_order_date < broker_order_date,
                )
            )
        )
        for row in rows:
            row.state = "CANCELED"
            row.message = "Expired at the end of the prior trading day"
            entry = await self.session.scalar(
                select(StrategyEntry).where(StrategyEntry.exit_order_id == row.id)
            )
            if entry is not None:
                entry.exit_order_id = None
        if rows:
            await self.session.commit()

    async def daily_realized_pnl(self, broker_order_date: str) -> tuple[Decimal, bool]:
        rows = list(
            await self.session.scalars(
                select(OrderRecord).where(
                    OrderRecord.broker_order_date == broker_order_date,
                    OrderRecord.side == "SELL",
                    OrderRecord.filled_quantity > 0,
                )
            )
        )
        synchronized = all(
            row.reference_cost_price is not None and row.average_fill_price is not None
            for row in rows
        )
        pnl = sum(
            (
                (Decimal(row.average_fill_price) - Decimal(row.reference_cost_price))
                * row.filled_quantity
            )
            for row in rows
            if row.reference_cost_price is not None and row.average_fill_price is not None
        )
        return Decimal(pnl), synchronized

    async def get_runtime_state(self, key: str, default: str = "") -> str:
        row = await self.session.get(RuntimeState, key)
        return row.value if row is not None else default

    async def set_runtime_state(self, key: str, value: str) -> None:
        row = await self.session.get(RuntimeState, key)
        if row is None:
            self.session.add(RuntimeState(key=key, value=value))
        else:
            row.value = value
        await self.session.commit()

    async def sync_listed_stocks(self, stocks: list[ParsedListedStock]) -> int:
        incoming = {stock.symbol: stock for stock in stocks}
        existing = {
            stock.symbol: stock
            for stock in await self.session.scalars(select(ListedStock))
        }
        changed = 0
        for symbol, stock in incoming.items():
            row = existing.get(symbol)
            if row is None:
                self.session.add(
                    ListedStock(
                        symbol=stock.symbol,
                        name=stock.name,
                        market=stock.market,
                        sector=stock.sector,
                        product=stock.product,
                    )
                )
                changed += 1
                continue
            if (
                row.name != stock.name
                or row.market != stock.market
                or row.sector != stock.sector
                or row.product != stock.product
            ):
                row.name = stock.name
                row.market = stock.market
                row.sector = stock.sector
                row.product = stock.product
                changed += 1
        stale = set(existing) - set(incoming)
        if stale:
            await self.session.execute(delete(ListedStock).where(ListedStock.symbol.in_(stale)))
            changed += len(stale)
        await self.session.commit()
        return changed

    async def search_listed_stocks(self, query: str, limit: int = 20) -> list[ListedStock]:
        normalized = query.strip()
        if not normalized:
            return []
        pattern = f"%{normalized}%"
        starts = f"{normalized}%"
        rows = await self.session.scalars(
            select(ListedStock)
            .where(
                or_(
                    ListedStock.symbol.like(pattern),
                    ListedStock.name.like(pattern),
                    ListedStock.market.like(pattern),
                )
            )
            .order_by(
                case((ListedStock.symbol == normalized, 0), (ListedStock.name == normalized, 1), else_=2),
                case((ListedStock.symbol.like(starts), 0), (ListedStock.name.like(starts), 1), else_=2),
                ListedStock.symbol,
            )
            .limit(limit)
        )
        return list(rows)

    async def market_bars(self, symbol: str, period: str) -> list[MarketBarRecord]:
        rows = await self.session.scalars(
            select(MarketBarRecord)
            .where(MarketBarRecord.symbol == symbol, MarketBarRecord.period == period)
            .order_by(MarketBarRecord.time)
        )
        return list(rows)

    async def upsert_market_bars(
        self,
        symbol: str,
        period: str,
        bars: list[dict],
        *,
        source: str = "KIS",
    ) -> int:
        if not bars:
            return 0
        times = [str(bar["time"]) for bar in bars]
        existing = {
            row.time: row
            for row in await self.session.scalars(
                select(MarketBarRecord).where(
                    MarketBarRecord.symbol == symbol,
                    MarketBarRecord.period == period,
                    MarketBarRecord.time.in_(times),
                )
            )
        }
        changed = 0
        for bar in bars:
            time = str(bar["time"])
            row = existing.get(time)
            if row is None:
                self.session.add(
                    MarketBarRecord(
                        symbol=symbol,
                        period=period,
                        time=time,
                        open=Decimal(bar["open"]),
                        high=Decimal(bar["high"]),
                        low=Decimal(bar["low"]),
                        close=Decimal(bar["close"]),
                        volume=int(bar["volume"]),
                        source=source,
                    )
                )
                changed += 1
                continue
            row.open = Decimal(bar["open"])
            row.high = Decimal(bar["high"])
            row.low = Decimal(bar["low"])
            row.close = Decimal(bar["close"])
            row.volume = int(bar["volume"])
            row.source = source
            changed += 1
        await self.session.commit()
        return changed

    async def record_strategy_entry(self, symbol: str, order_id: str) -> bool:
        trading_date = date.today().isoformat()
        existing = await self.session.scalar(
            select(StrategyEntry).where(
                StrategyEntry.trading_date == trading_date,
                StrategyEntry.symbol == symbol,
            )
        )
        if existing is not None:
            return False
        self.session.add(
            StrategyEntry(trading_date=trading_date, symbol=symbol, entry_order_id=order_id)
        )
        await self.session.commit()
        return True

    async def strategy_entry(self, symbol: str) -> StrategyEntry | None:
        return await self.session.scalar(
            select(StrategyEntry).where(
                StrategyEntry.trading_date == date.today().isoformat(),
                StrategyEntry.symbol == symbol,
            )
        )

    async def open_strategy_entry(self, symbol: str) -> StrategyEntry | None:
        return await self.session.scalar(
            select(StrategyEntry)
            .where(StrategyEntry.symbol == symbol, StrategyEntry.closed.is_(False))
            .order_by(desc(StrategyEntry.created_at))
        )

    async def mark_strategy_exit(self, entry: StrategyEntry, order_id: str) -> None:
        entry.exit_order_id = order_id
        await self.session.commit()

    async def close_strategy_entry_by_exit(self, order_id: str) -> None:
        entry = await self.session.scalar(
            select(StrategyEntry).where(StrategyEntry.exit_order_id == order_id)
        )
        if entry is not None:
            entry.closed = True
            await self.session.commit()
