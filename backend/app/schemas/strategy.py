from pydantic import BaseModel


class StrategyStatus(BaseModel):
    name: str
    enabled: bool
    signal_only: bool = True
    status: str = "IDLE"


class AutomationRequest(BaseModel):
    enabled: bool

