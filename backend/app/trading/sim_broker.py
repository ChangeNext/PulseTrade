from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from app.config import Settings
from app.db.models import OrderRecord
from app.db.repository import TradingRepository
from app.strategies.base import OrderBookSnapshot
from app.trading.execution_engine import ExecutionEngine


class SimBroker:
    """호가 기반 지정가 체결, 부분체결, 비용 및 포지션을 재현하는 SIM 브로커."""

    def __init__(self, settings: Settings, engine: ExecutionEngine) -> None:
        self.settings = settings
        self.engine = engine
        self.engine.context.available_cash = Decimal(settings.sim_initial_cash_krw)

    async def restore(self, repository: TradingRepository) -> None:
        context = self.engine.context
        context.available_cash = Decimal(self.settings.sim_initial_cash_krw)
        context.position_quantities = {}
        context.position_average_prices = {}
        context.position_current_prices = {}
        context.position_amounts = {}
        context.daily_realized_pnl = Decimal("0")
        today = datetime.now().strftime("%Y%m%d")
        for order in await repository.sim_orders():
            if order.filled_quantity <= 0 or order.average_fill_price is None:
                continue
            self._apply_position_fill(
                order.side,
                order.symbol,
                order.filled_quantity,
                Decimal(order.average_fill_price),
                Decimal(order.commission),
                Decimal(order.tax),
                count_pnl=order.broker_order_date == today,
            )
        context.daily_order_count = sum(
            1 for order in await repository.sim_orders() if order.broker_order_date == today
        )
        active = await repository.active_sim_orders()
        context.pending_symbols = {row.symbol for row in active if row.side == "BUY"}
        context.active_order_keys = {f"{row.symbol}:{row.side}" for row in active}
        context.pending_sell_quantities = {}
        for row in active:
            if row.side == "SELL":
                context.pending_sell_quantities[row.symbol] = (
                    context.pending_sell_quantities.get(row.symbol, 0)
                    + max(row.quantity - row.filled_quantity, 0)
                )

    async def on_orderbook(
        self, symbol: str, book: OrderBookSnapshot, repository: TradingRepository
    ) -> None:
        midpoint = (book.best_ask + book.best_bid) / Decimal("2")
        self.engine.context.position_current_prices[symbol] = midpoint
        if symbol in self.engine.context.position_quantities:
            self.engine.context.position_amounts[symbol] = (
                midpoint * self.engine.context.position_quantities[symbol]
            )
        ask_liquidity = book.best_ask_quantity
        bid_liquidity = book.best_bid_quantity
        for order in await repository.active_sim_orders(symbol):
            if not self._latency_elapsed(order):
                continue
            remaining = order.quantity - order.filled_quantity
            if remaining <= 0:
                continue
            if order.side == "BUY":
                if order.price < book.best_ask or ask_liquidity <= 0:
                    continue
                fill_quantity = min(remaining, ask_liquidity)
                fill_price = book.best_ask
                ask_liquidity -= fill_quantity
            else:
                if order.price > book.best_bid or bid_liquidity <= 0:
                    continue
                fill_quantity = min(remaining, bid_liquidity)
                fill_price = book.best_bid
                bid_liquidity -= fill_quantity
            await self._fill(repository, order, fill_quantity, fill_price)

    async def _fill(
        self,
        repository: TradingRepository,
        order: OrderRecord,
        quantity: int,
        price: Decimal,
    ) -> None:
        previous_quantity = order.filled_quantity
        total_quantity = previous_quantity + quantity
        previous_value = Decimal(order.average_fill_price or 0) * previous_quantity
        average_price = (previous_value + price * quantity) / total_quantity
        gross = price * quantity
        commission = self._cost(gross, Decimal(str(self.settings.sim_commission_bps)))
        tax = (
            self._cost(gross, Decimal(str(self.settings.sim_sell_tax_bps)))
            if order.side == "SELL"
            else Decimal("0")
        )
        state = "FILLED" if total_quantity >= order.quantity else "PARTIALLY_FILLED"
        await repository.update_order(
            order,
            state=state,
            broker_order_date=datetime.now().strftime("%Y%m%d"),
            filled_quantity=total_quantity,
            average_fill_price=average_price,
            commission=Decimal(order.commission) + commission,
            tax=Decimal(order.tax) + tax,
            message=f"SIM {state.lower()} at {price}",
        )
        await repository.add_fill_once(
            fill_key=f"sim:{order.id}:{total_quantity}:{price}",
            order_id=order.id,
            quantity=quantity,
            price=price,
        )
        self._apply_position_fill(order.side, order.symbol, quantity, price, commission, tax)
        if state == "FILLED":
            self.engine.context.active_order_keys.discard(f"{order.symbol}:{order.side}")
            if order.side == "BUY":
                self.engine.context.pending_symbols.discard(order.symbol)
            else:
                self.engine.context.pending_sell_quantities[order.symbol] = max(
                    self.engine.context.pending_sell_quantities.get(order.symbol, 0) - quantity, 0
                )

    def _apply_position_fill(
        self,
        side: str,
        symbol: str,
        quantity: int,
        price: Decimal,
        commission: Decimal,
        tax: Decimal,
        *,
        count_pnl: bool = True,
    ) -> None:
        context = self.engine.context
        old_quantity = context.position_quantities.get(symbol, 0)
        old_average = context.position_average_prices.get(symbol, Decimal("0"))
        gross = price * quantity
        if side == "BUY":
            new_quantity = old_quantity + quantity
            new_average = (
                (old_average * old_quantity + gross + commission) / new_quantity
                if new_quantity > 0
                else Decimal("0")
            )
            context.position_quantities[symbol] = new_quantity
            context.position_average_prices[symbol] = new_average
            context.position_current_prices[symbol] = price
            context.position_amounts[symbol] = new_average * new_quantity
            if context.available_cash is not None:
                context.available_cash -= gross + commission
        else:
            sold = min(quantity, old_quantity)
            if count_pnl:
                context.daily_realized_pnl += (price - old_average) * sold - commission - tax
            new_quantity = max(old_quantity - sold, 0)
            context.position_quantities[symbol] = new_quantity
            if new_quantity == 0:
                context.position_average_prices.pop(symbol, None)
                context.position_current_prices.pop(symbol, None)
                context.position_amounts.pop(symbol, None)
            else:
                context.position_amounts[symbol] = old_average * new_quantity
            if context.available_cash is not None:
                context.available_cash += gross - commission - tax

    def _latency_elapsed(self, order: OrderRecord) -> bool:
        created = order.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        elapsed_ms = (datetime.now(timezone.utc) - created).total_seconds() * 1000
        return elapsed_ms >= self.settings.sim_latency_ms

    @staticmethod
    def _cost(gross: Decimal, bps: Decimal) -> Decimal:
        return (gross * bps / Decimal("10000")).quantize(Decimal("0.01"), ROUND_HALF_UP)
