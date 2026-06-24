from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


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
class StrategySignal:
    strategy: str
    symbol: str
    action: str
    reason: str


class Strategy(ABC):
    @abstractmethod
    def evaluate(self, snapshot: MarketSnapshot) -> StrategySignal | None:
        pass

