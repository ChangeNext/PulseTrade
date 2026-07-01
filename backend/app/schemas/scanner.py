from decimal import Decimal

from pydantic import BaseModel, Field


class ScannerCandidateResponse(BaseModel):
    symbol: str
    name: str = ""
    price: Decimal
    change_pct: Decimal
    volume: int
    trade_value: Decimal
    vwap: Decimal
    volume_spike: Decimal
    spread_bps: Decimal
    score: Decimal
    passed: bool
    reasons: list[str] = Field(default_factory=list)


class ScannerResponse(BaseModel):
    universe_size: int
    candidates: list[ScannerCandidateResponse]
