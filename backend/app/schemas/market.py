from decimal import Decimal

from pydantic import BaseModel, Field


class MarketQuote(BaseModel):
    symbol: str
    name: str = ""
    price: Decimal
    volume: int


class MarketBar(BaseModel):
    time: str
    open: Decimal
    price: Decimal
    high: Decimal
    low: Decimal
    volume: int


class OrderBookView(BaseModel):
    symbol: str
    best_ask: Decimal
    best_bid: Decimal
    total_ask_quantity: int
    total_bid_quantity: int
    best_ask_quantity: int = 0
    best_bid_quantity: int = 0
    spread_bps: Decimal
    imbalance: Decimal
    received_at: str | None = None
    source: str = "REST"


class MarketRankingRow(BaseModel):
    rank: int
    symbol: str
    name: str = ""
    price: Decimal = Decimal("0")
    change_pct: Decimal = Decimal("0")
    volume: int = 0
    trade_value: Decimal = Decimal("0")
    score: Decimal = Decimal("0")
    source: str = ""


class MarketRankingResponse(BaseModel):
    type: str
    rows: list[MarketRankingRow] = Field(default_factory=list)


class StockProfile(BaseModel):
    symbol: str
    name: str = ""
    market: str = ""
    sector: str = ""
    product: str = ""
    listed_shares: int = 0
    capital: Decimal = Decimal("0")
    par_value: Decimal = Decimal("0")


class MarketIndexView(BaseModel):
    symbol: str
    name: str
    price: Decimal
    change_pct: Decimal
    score: Decimal = Decimal("0")
    ready: bool = True
    reason: str = ""


class MarketSessionView(BaseModel):
    is_trading_day: bool
    market_state: str
    websocket_market_state: str | None = None
    updated_at: str


class StockSearchResult(BaseModel):
    symbol: str
    name: str
    market: str
    sector: str = ""
    product: str = ""
