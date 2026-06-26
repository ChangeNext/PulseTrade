from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


@dataclass(frozen=True)
class MarketSnapshot:
    symbol: str
    timestamp: datetime
    price: Decimal
    opening_range_high: Decimal
    vwap: Decimal
    current_volume: int
    average_volume: Decimal
    already_held: bool = False
    has_pending_order: bool = False


@dataclass(frozen=True)
class PriceBar:
    time: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


@dataclass(frozen=True)
class MarketIndexSnapshot:
    name: str
    symbol: str
    price: Decimal
    change_pct: Decimal
    score: Decimal
    ready: bool
    reason: str


@dataclass(frozen=True)
class StrategySignal:
    strategy: str
    symbol: str
    action: str
    reason: str


class SignalAction(StrEnum):
    BUY = "BUY"
    WAIT = "WAIT"
    SELL = "SELL"
    EXIT = "EXIT"


@dataclass(frozen=True)
class OrderBookSnapshot:
    best_ask: Decimal
    best_bid: Decimal
    total_ask_quantity: int
    total_bid_quantity: int
    best_ask_quantity: int = 0
    best_bid_quantity: int = 0
    received_at: datetime | None = None


@dataclass(frozen=True)
class SignalContext:
    market: MarketSnapshot
    orderbook: OrderBookSnapshot | None
    trade_strength: Decimal | None
    recent_prices: tuple[Decimal, ...]
    intraday_bars: tuple[PriceBar, ...] = ()
    daily_bars: tuple[PriceBar, ...] = ()
    market_indices: tuple[MarketIndexSnapshot, ...] = ()
    already_held: bool = False
    has_pending_order: bool = False
    trading_halted: bool = False
    vi_active: bool = False


@dataclass(frozen=True)
class ComponentSignal:
    name: str
    score: Decimal
    ready: bool
    reason: str


@dataclass(frozen=True)
class ScoredSignal:
    symbol: str
    action: SignalAction
    score: Decimal
    components: tuple[ComponentSignal, ...]
    reason: str


class SignalComponent(ABC):
    name: str

    @abstractmethod
    def evaluate(self, context: SignalContext) -> ComponentSignal:
        pass


class Strategy(ABC):
    @abstractmethod
    def evaluate(self, snapshot: MarketSnapshot) -> StrategySignal | None:
        pass
