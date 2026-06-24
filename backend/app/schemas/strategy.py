from pydantic import BaseModel, Field


class ComponentScore(BaseModel):
    name: str
    score: float
    ready: bool
    reason: str


class SignalScore(BaseModel):
    symbol: str
    action: str
    score: float
    reason: str
    components: list[ComponentScore]


class StrategyStatus(BaseModel):
    name: str
    enabled: bool
    signal_only: bool = True
    status: str = "IDLE"
    auto_order_enabled: bool = False
    desired_enabled: bool = False
    ready: bool = False
    readiness_reason: str | None = None
    watched_symbols: list[str] = Field(default_factory=list)
    signals: list[SignalScore] = Field(default_factory=list)


class AutomationRequest(BaseModel):
    enabled: bool
