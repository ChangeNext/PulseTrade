import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.config import Settings
from app.db.repository import TradingRepository
from app.db.session import AsyncSessionFactory
from app.kis.market import KISMarketService, MinuteBar
from app.kis.websocket import KISWebSocketClient, OrderBookTick, RealtimeTick
from app.schemas.order import ManualOrderRequest
from app.strategies.base import (
    MarketSnapshot,
    OrderBookSnapshot,
    ScoredSignal,
    SignalAction,
    SignalContext,
)
from app.strategies.momentum_score import MomentumScore
from app.strategies.opening_range_breakout import ORBStrategy
from app.strategies.orderbook_imbalance import OrderbookImbalanceStrategy
from app.strategies.risk_filter import StrategyRiskFilter
from app.strategies.signal_scorer import SignalScorer
from app.strategies.trade_strength import TradeStrengthStrategy
from app.strategies.trend_alignment import TrendAlignmentStrategy
from app.strategies.volume_spike import VolumeSpikeStrategy
from app.strategies.vwap_filter import VWAPFilter
from app.trading.execution_engine import ExecutionEngine
from app.trading.order_state import OrderState
from app.trading.order_supervisor import OrderSupervisor
from app.trading.sim_broker import SimBroker

KST = timezone(timedelta(hours=9))


@dataclass
class SymbolBars:
    bars: dict[str, MinuteBar] = field(default_factory=dict)

    def add_tick(self, tick: RealtimeTick, now: datetime) -> None:
        minute = now.strftime("%H%M00")
        price = Decimal(tick.price)
        existing = self.bars.get(minute)
        if existing is None:
            self.bars[minute] = MinuteBar(tick.symbol, minute, price, price, price, tick.volume)
        else:
            self.bars[minute] = MinuteBar(
                tick.symbol,
                minute,
                price,
                max(existing.high, price),
                min(existing.low, price),
                existing.volume + tick.volume,
            )

    def recent_prices(self) -> tuple[Decimal, ...]:
        return tuple(self.bars[key].price for key in sorted(self.bars))

    def snapshot(self, symbol: str, now: datetime) -> MarketSnapshot | None:
        ordered = [self.bars[key] for key in sorted(self.bars)]
        opening = [bar for bar in ordered if "090000" <= bar.time < "090500"]
        if not opening or len(ordered) < 21:
            return None
        current = ordered[-1]
        previous = ordered[-21:-1]
        total_volume = sum(bar.volume for bar in ordered)
        if total_volume <= 0:
            return None
        vwap = sum(bar.price * bar.volume for bar in ordered) / Decimal(total_volume)
        average_volume = Decimal(sum(bar.volume for bar in previous)) / Decimal(len(previous))
        return MarketSnapshot(
            symbol=symbol,
            timestamp=now,
            price=current.price,
            opening_range_high=max(bar.high for bar in opening),
            vwap=vwap,
            current_volume=current.volume,
            average_volume=average_volume,
        )


class StrategyRuntime:
    def __init__(
        self,
        settings: Settings,
        engine: ExecutionEngine,
        market: KISMarketService,
        websocket: KISWebSocketClient,
        sim_broker: SimBroker | None = None,
    ) -> None:
        self.settings = settings
        self.engine = engine
        self.market = market
        self.websocket = websocket
        self.sim_broker = sim_broker
        self.order_supervisor = OrderSupervisor(settings, engine)
        self.symbols = settings.strategy_symbol_list
        self.series = {symbol: SymbolBars() for symbol in self.symbols}
        self.orderbooks: dict[str, OrderBookSnapshot] = {}
        self.trade_strengths: dict[str, Decimal] = {}
        self.trading_halts: dict[str, bool] = {}
        self.last_ticks: dict[str, tuple[Decimal, datetime]] = {}
        self.volatility_blocked_until: dict[str, datetime] = {}
        self.vi_states: dict[str, bool] = {}
        self.vi_refreshing: set[str] = set()
        self.vi_checked_at: dict[str, datetime] = {}
        self.latest_signals: dict[str, ScoredSignal] = {}
        self._last_actions: dict[str, SignalAction] = {}
        self.scorer = SignalScorer(
            (
                VolumeSpikeStrategy(Decimal(str(settings.strategy_volume_multiplier))),
                VWAPFilter(),
                ORBStrategy(),
                OrderbookImbalanceStrategy(),
                TradeStrengthStrategy(),
                MomentumScore(),
                TrendAlignmentStrategy(),
            ),
            {
                "volume_spike": Decimal(str(settings.signal_weight_volume)),
                "vwap": Decimal(str(settings.signal_weight_vwap)),
                "opening_range_breakout": Decimal(str(settings.signal_weight_orb)),
                "orderbook_imbalance": Decimal(str(settings.signal_weight_orderbook)),
                "trade_strength": Decimal(str(settings.signal_weight_trade_strength)),
                "momentum": Decimal(str(settings.signal_weight_momentum)),
                "trend_alignment": Decimal(str(settings.signal_weight_trend)),
            },
            buy_threshold=Decimal(str(settings.signal_buy_threshold)),
            sell_threshold=Decimal(str(settings.signal_sell_threshold)),
            exit_threshold=Decimal(str(settings.signal_exit_threshold)),
            risk_filter=StrategyRiskFilter(
                max_spread_bps=Decimal(str(settings.max_spread_bps)),
                max_quote_age_seconds=Decimal(str(settings.max_quote_age_seconds)),
            ),
        )
        self.ready = False
        self.last_error: str | None = None
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        if not self.symbols:
            self.ready = False
            self.last_error = "STRATEGY_SYMBOLS has no valid 6-digit symbols"
            return
        for symbol in self.symbols:
            bars = await self.market.get_minute_bars(symbol)
            self.series[symbol].bars = {bar.time: bar for bar in bars}
        bars_ready = all(
            self.series[symbol].snapshot(symbol, datetime.now(KST)) is not None
            for symbol in self.symbols
        )
        self.ready = bars_ready and all(symbol in self.orderbooks for symbol in self.symbols)
        self.last_error = None if self.ready else "Waiting for intraday bars and realtime order books"

    async def run(self) -> None:
        delay = 1.0
        while True:
            try:
                await self.initialize()
                async for event in self.websocket.stream_market(self.symbols):
                    self.engine.context.websocket_connected = True
                    if isinstance(event, RealtimeTick):
                        self.trade_strengths[event.symbol] = event.trade_strength
                        self.trading_halts[event.symbol] = event.trading_halted
                        self._update_volatility_guard(event)
                        self.series[event.symbol].add_tick(event, datetime.now(KST))
                        await self.evaluate_symbol(event.symbol)
                    elif isinstance(event, OrderBookTick):
                        self.orderbooks[event.symbol] = OrderBookSnapshot(
                            best_ask=event.best_ask,
                            best_bid=event.best_bid,
                            total_ask_quantity=event.total_ask_quantity,
                            total_bid_quantity=event.total_bid_quantity,
                            best_ask_quantity=event.best_ask_quantity,
                            best_bid_quantity=event.best_bid_quantity,
                            received_at=event.received_at,
                        )
                        if self.sim_broker is not None:
                            async with AsyncSessionFactory() as session:
                                await self.sim_broker.on_orderbook(
                                    event.symbol,
                                    self.orderbooks[event.symbol],
                                    TradingRepository(session),
                                )
                        async with AsyncSessionFactory() as session:
                            await self.order_supervisor.sweep(
                                event.symbol,
                                self.orderbooks[event.symbol],
                                TradingRepository(session),
                            )
                        await self.evaluate_symbol(event.symbol)
                raise ConnectionError("KIS WebSocket stream ended")
            except asyncio.CancelledError:
                raise
            except Exception as error:
                self.engine.context.websocket_connected = False
                self.ready = False
                self.last_error = str(error)
                self.engine.refresh_effective_automation(False)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30)
            else:
                delay = 1.0

    async def on_tick(self, tick: RealtimeTick) -> None:
        self.trade_strengths[tick.symbol] = tick.trade_strength
        self.trading_halts[tick.symbol] = tick.trading_halted
        self._update_volatility_guard(tick)
        self.series[tick.symbol].add_tick(tick, datetime.now(KST))
        await self.evaluate_symbol(tick.symbol)

    async def evaluate_symbol(self, symbol: str) -> None:
        now = datetime.now(KST)
        series = self.series.get(symbol)
        if series is None:
            return
        market = series.snapshot(symbol, now)
        if market is None:
            self.ready = False
            return
        last_vi_check = self.vi_checked_at.get(symbol)
        if (
            symbol not in self.vi_refreshing
            and (last_vi_check is None or (now - last_vi_check).total_seconds() >= 5)
        ):
            self.vi_refreshing.add(symbol)
            asyncio.create_task(self._refresh_vi(symbol))
        broker_vi_active = self.vi_states.get(symbol, True)
        context = SignalContext(
            market=market,
            orderbook=self.orderbooks.get(symbol),
            trade_strength=self.trade_strengths.get(symbol),
            recent_prices=series.recent_prices(),
            already_held=self.engine.context.position_quantities.get(symbol, 0) > 0,
            has_pending_order=symbol in self.engine.context.pending_symbols,
            trading_halted=self.trading_halts.get(symbol, False),
            vi_active=(
                broker_vi_active
                or datetime.now(KST)
                < self.volatility_blocked_until.get(symbol, datetime.min.replace(tzinfo=KST))
            ),
        )
        signal = self.scorer.evaluate(context)
        self.latest_signals[symbol] = signal
        self.ready = all(
            item in self.orderbooks and item in self.trade_strengths for item in self.symbols
        )
        self.last_error = None if self.ready else "Waiting for realtime order books/trade strength"
        self.engine.refresh_effective_automation(self.ready)
        await self._record_action_change(signal)
        if not self.engine.automation_enabled:
            return
        async with self._lock:
            time_exit_reason = await self._time_exit_reason(context)
            if time_exit_reason is not None:
                await self._submit_exit(context, SignalAction.EXIT, time_exit_reason)
                return
            if await self._evaluate_stop_take(context):
                return
            current_time = now.strftime("%H%M%S")
            if signal.action == SignalAction.BUY and "090500" <= current_time <= "151000":
                await self._submit_entry(context, signal)
            elif signal.action in {SignalAction.SELL, SignalAction.EXIT}:
                await self._submit_signal_exit(context, signal)

    async def _record_action_change(self, signal: ScoredSignal) -> None:
        if self._last_actions.get(signal.symbol) == signal.action:
            return
        self._last_actions[signal.symbol] = signal.action
        component_scores = {item.name: str(item.score) for item in signal.components}
        async with AsyncSessionFactory() as session:
            await TradingRepository(session).add_event(
                "STRATEGY_SIGNAL",
                f"{signal.symbol} {signal.action} score={signal.score}",
                {"symbol": signal.symbol, "action": signal.action, "score": signal.score, "components": component_scores},
            )
        if signal.action != SignalAction.WAIT:
            await self.engine.notifier.send(
                "STRATEGY_SIGNAL", f"{signal.symbol} {signal.action} score={signal.score}"
            )

    async def _submit_entry(self, context: SignalContext, signal: ScoredSignal) -> None:
        price = context.orderbook.best_ask if context.orderbook and context.orderbook.best_ask > 0 else context.market.price
        quantity = int(Decimal(self.settings.auto_order_budget_krw) / price)
        if quantity <= 0:
            return
        key = f"strategy:{datetime.now(KST).date()}:{context.market.symbol}:entry"
        async with AsyncSessionFactory() as session:
            repository = TradingRepository(session)
            if await repository.strategy_entry(context.market.symbol) is not None:
                return
            response = await self.engine.submit_manual(
                ManualOrderRequest(symbol=context.market.symbol, side="BUY", quantity=quantity, price=price),
                repository,
                key,
                source="STRATEGY",
                strategy_name="SIGNAL_SCORER",
            )
            if response.state in {OrderState.ORDER_SENT, OrderState.RECONCILING}:
                await repository.record_strategy_entry(context.market.symbol, response.order_id)

    async def _evaluate_stop_take(self, context: SignalContext) -> bool:
        symbol = context.market.symbol
        quantity = self.engine.context.position_quantities.get(symbol, 0)
        average_price = self.engine.context.position_average_prices.get(symbol, Decimal("0"))
        if quantity <= 0 or average_price <= 0:
            return False
        change_pct = (context.market.price - average_price) / average_price * Decimal("100")
        if not (
            change_pct <= Decimal(str(self.settings.strategy_stop_loss_pct))
            or change_pct >= Decimal(str(self.settings.strategy_take_profit_pct))
        ):
            return False
        action = SignalAction.EXIT
        reason = f"Stop/take threshold reached at {change_pct:.2f}%"
        return await self._submit_exit(context, action, reason)

    async def _time_exit_reason(self, context: SignalContext) -> str | None:
        symbol = context.market.symbol
        if self.engine.context.position_quantities.get(symbol, 0) <= 0:
            return None
        now = datetime.now(KST)
        if now.strftime("%H%M%S") >= self.settings.strategy_force_exit_time:
            return f"Forced intraday exit at {self.settings.strategy_force_exit_time}"
        async with AsyncSessionFactory() as session:
            entry = await TradingRepository(session).open_strategy_entry(symbol)
            if entry is None:
                return None
            created = entry.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            held_minutes = (now - created.astimezone(KST)).total_seconds() / 60
            if held_minutes >= self.settings.strategy_max_holding_minutes:
                return f"Maximum holding time reached ({held_minutes:.1f}m)"
        return None

    async def _submit_signal_exit(self, context: SignalContext, signal: ScoredSignal) -> None:
        await self._submit_exit(context, signal.action, signal.reason)

    async def _submit_exit(
        self, context: SignalContext, action: SignalAction, reason: str
    ) -> bool:
        symbol = context.market.symbol
        quantity = self.engine.context.position_quantities.get(symbol, 0)
        if quantity <= 0:
            return False
        price = context.orderbook.best_bid if context.orderbook and context.orderbook.best_bid > 0 else context.market.price
        key = f"strategy:{datetime.now(KST).date()}:{symbol}:exit"
        async with AsyncSessionFactory() as session:
            repository = TradingRepository(session)
            entry = await repository.open_strategy_entry(symbol)
            if entry is None or entry.exit_order_id is not None:
                return False
            response = await self.engine.submit_manual(
                ManualOrderRequest(symbol=symbol, side="SELL", quantity=quantity, price=price),
                repository,
                key,
                source="EXIT",
                strategy_name=f"SIGNAL_SCORER:{action}",
            )
            await repository.add_event(
                "STRATEGY_EXIT", reason, {"symbol": symbol, "action": action, "order_id": response.order_id}
            )
            if response.state in {OrderState.ORDER_SENT, OrderState.RECONCILING}:
                await repository.mark_strategy_exit(entry, response.order_id)
                return True
        return False

    def signal_payloads(self) -> list[dict]:
        return [
            {
                "symbol": signal.symbol,
                "action": signal.action,
                "score": signal.score,
                "reason": signal.reason,
                "components": [
                    {"name": item.name, "score": item.score, "ready": item.ready, "reason": item.reason}
                    for item in signal.components
                ],
            }
            for signal in self.latest_signals.values()
        ]

    def _update_volatility_guard(self, tick: RealtimeTick) -> None:
        now = datetime.now(KST)
        price = Decimal(tick.price)
        previous = self.last_ticks.get(tick.symbol)
        self.last_ticks[tick.symbol] = (price, now)
        if previous is None or previous[0] <= 0:
            return
        previous_price, previous_time = previous
        if (now - previous_time).total_seconds() > 60:
            return
        move_pct = abs(price - previous_price) / previous_price * Decimal("100")
        if move_pct >= Decimal(str(self.settings.volatility_guard_move_pct)):
            self.volatility_blocked_until[tick.symbol] = now + timedelta(
                seconds=self.settings.volatility_guard_cooldown_seconds
            )

    async def _refresh_vi(self, symbol: str) -> None:
        try:
            self.vi_states[symbol] = await self.market.is_vi_active(symbol)
        except Exception:
            self.vi_states[symbol] = True
        finally:
            self.vi_checked_at[symbol] = datetime.now(KST)
            self.vi_refreshing.discard(symbol)
