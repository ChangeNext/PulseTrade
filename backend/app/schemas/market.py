from decimal import Decimal

from pydantic import BaseModel


class MarketQuote(BaseModel):
    symbol: str
    name: str = ""
    price: Decimal
    volume: int


class MarketBar(BaseModel):
    time: str
    price: Decimal
    high: Decimal
    low: Decimal
    volume: int
