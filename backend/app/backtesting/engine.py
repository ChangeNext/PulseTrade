from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from app.config import Settings
from app.strategies.base import MarketSnapshot, OrderBookSnapshot, SignalAction, SignalContext
from app.strategies.momentum_score import MomentumScore
from app.strategies.opening_range_breakout import ORBStrategy
from app.strategies.orderbook_imbalance import OrderbookImbalanceStrategy
from app.strategies.risk_filter import StrategyRiskFilter
from app.strategies.signal_scorer import SignalScorer
from app.strategies.trade_strength import TradeStrengthStrategy
from app.strategies.volume_spike import VolumeSpikeStrategy
from app.strategies.vwap_filter import VWAPFilter


@dataclass(frozen=True)
class BacktestBar:
    timestamp: datetime
    symbol: str
    close: Decimal
    high: Decimal
    low: Decimal
    volume: int
    best_ask: Decimal
    best_bid: Decimal
    ask_quantity: int
    bid_quantity: int
    trade_strength: Decimal
    halted: bool = False


@dataclass(frozen=True)
class BacktestTrade:
    symbol: str
    entry_time: datetime
    exit_time: datetime
    quantity: int
    entry_price: Decimal
    exit_price: Decimal
    gross_pnl: Decimal
    costs: Decimal
    net_pnl: Decimal
    exit_reason: str


@dataclass(frozen=True)
class BacktestResult:
    trades: tuple[BacktestTrade, ...]
    net_pnl: Decimal
    win_rate: Decimal
    max_drawdown: Decimal


class BacktestEngine:
    def __init__(self, settings: Settings, *, slippage_bps: Decimal = Decimal("5")) -> None:
        self.settings = settings
        self.slippage_bps = slippage_bps
        self.scorer = SignalScorer(
            (
                VolumeSpikeStrategy(Decimal(str(settings.strategy_volume_multiplier))),
                VWAPFilter(), ORBStrategy(), OrderbookImbalanceStrategy(),
                TradeStrengthStrategy(), MomentumScore(),
            ),
            {
                "volume_spike": Decimal(str(settings.signal_weight_volume)),
                "vwap": Decimal(str(settings.signal_weight_vwap)),
                "opening_range_breakout": Decimal(str(settings.signal_weight_orb)),
                "orderbook_imbalance": Decimal(str(settings.signal_weight_orderbook)),
                "trade_strength": Decimal(str(settings.signal_weight_trade_strength)),
                "momentum": Decimal(str(settings.signal_weight_momentum)),
            },
            buy_threshold=Decimal(str(settings.signal_buy_threshold)),
            sell_threshold=Decimal(str(settings.signal_sell_threshold)),
            exit_threshold=Decimal(str(settings.signal_exit_threshold)),
            risk_filter=StrategyRiskFilter(max_spread_bps=Decimal(str(settings.max_spread_bps))),
        )

    def run(self, bars: list[BacktestBar]) -> BacktestResult:
        symbols = {bar.symbol for bar in bars}
        if len(symbols) > 1:
            raise ValueError("Run one symbol per backtest to avoid cross-symbol capital leakage")
        ordered = sorted(bars, key=lambda item: item.timestamp)
        prices: list[Decimal] = []
        volumes: list[int] = []
        session_value = Decimal("0")
        session_volume = 0
        opening_high = Decimal("0")
        position: tuple[datetime, int, Decimal, Decimal] | None = None
        trades: list[BacktestTrade] = []
        equity = Decimal("0")
        peak = Decimal("0")
        max_drawdown = Decimal("0")
        current_date = None

        for bar in ordered:
            if current_date != bar.timestamp.date():
                current_date = bar.timestamp.date()
                prices, volumes = [], []
                session_value, session_volume, opening_high = Decimal("0"), 0, Decimal("0")
            prices.append(bar.close)
            volumes.append(bar.volume)
            session_value += bar.close * bar.volume
            session_volume += bar.volume
            hhmmss = bar.timestamp.strftime("%H%M%S")
            if "090000" <= hhmmss < "090500":
                opening_high = max(opening_high, bar.high)
            if opening_high <= 0 or len(volumes) < 21 or session_volume <= 0:
                continue
            market = MarketSnapshot(
                symbol=bar.symbol,
                timestamp=bar.timestamp,
                price=bar.close,
                opening_range_high=opening_high,
                vwap=session_value / session_volume,
                current_volume=bar.volume,
                average_volume=Decimal(sum(volumes[-21:-1])) / Decimal("20"),
            )
            held = position is not None
            context = SignalContext(
                market=market,
                orderbook=OrderBookSnapshot(
                    bar.best_ask, bar.best_bid, bar.ask_quantity, bar.bid_quantity,
                    bar.ask_quantity, bar.bid_quantity, datetime.now(timezone.utc)
                ),
                trade_strength=bar.trade_strength,
                recent_prices=tuple(prices),
                already_held=held,
                trading_halted=bar.halted,
            )
            signal = self.scorer.evaluate(context)
            if position is None and signal.action == SignalAction.BUY and "090500" <= hhmmss <= "151000":
                entry_price = self._slipped(bar.best_ask, buy=True)
                quantity = int(Decimal(self.settings.auto_order_budget_krw) / entry_price)
                if quantity > 0:
                    entry_cost = self._commission(entry_price * quantity)
                    position = (bar.timestamp, quantity, entry_price, entry_cost)
                continue
            if position is None:
                continue
            entry_time, quantity, entry_price, entry_cost = position
            change_pct = (bar.close - entry_price) / entry_price * Decimal("100")
            held_minutes = (bar.timestamp - entry_time).total_seconds() / 60
            reason = None
            if change_pct <= Decimal(str(self.settings.strategy_stop_loss_pct)):
                reason = "STOP_LOSS"
            elif change_pct >= Decimal(str(self.settings.strategy_take_profit_pct)):
                reason = "TAKE_PROFIT"
            elif held_minutes >= self.settings.strategy_max_holding_minutes:
                reason = "MAX_HOLDING_TIME"
            elif hhmmss >= self.settings.strategy_force_exit_time:
                reason = "FORCED_INTRADAY_EXIT"
            elif signal.action in {SignalAction.SELL, SignalAction.EXIT}:
                reason = str(signal.action)
            if reason is None:
                continue
            exit_price = self._slipped(bar.best_bid, buy=False)
            gross_pnl = (exit_price - entry_price) * quantity
            exit_gross = exit_price * quantity
            costs = entry_cost + self._commission(exit_gross) + self._tax(exit_gross)
            net_pnl = gross_pnl - costs
            trades.append(
                BacktestTrade(
                    bar.symbol, entry_time, bar.timestamp, quantity, entry_price,
                    exit_price, gross_pnl, costs, net_pnl, reason
                )
            )
            equity += net_pnl
            peak = max(peak, equity)
            max_drawdown = max(max_drawdown, peak - equity)
            position = None

        wins = sum(1 for trade in trades if trade.net_pnl > 0)
        win_rate = Decimal(wins * 100) / Decimal(len(trades)) if trades else Decimal("0")
        return BacktestResult(tuple(trades), sum((t.net_pnl for t in trades), Decimal("0")), win_rate, max_drawdown)

    def _slipped(self, price: Decimal, *, buy: bool) -> Decimal:
        multiplier = Decimal("1") + (self.slippage_bps / Decimal("10000")) * (1 if buy else -1)
        return price * multiplier

    def _commission(self, gross: Decimal) -> Decimal:
        return gross * Decimal(str(self.settings.sim_commission_bps)) / Decimal("10000")

    def _tax(self, gross: Decimal) -> Decimal:
        return gross * Decimal(str(self.settings.sim_sell_tax_bps)) / Decimal("10000")
