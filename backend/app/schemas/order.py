from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.trading.order_state import OrderState


class ManualOrderRequest(BaseModel):
    symbol: str = Field(pattern=r"^\d{6}$", description="국내주식 6자리 종목코드")
    side: Literal["BUY", "SELL"]
    quantity: int = Field(gt=0)
    price: Decimal = Field(gt=0)
    live_confirmation: str | None = None


class OrderResponse(BaseModel):
    order_id: str
    mode: str
    state: OrderState
    message: str
    risk_reasons: list[str] = Field(default_factory=list)


class KillSwitchRequest(BaseModel):
    stopped: bool = True

