from decimal import Decimal

from pydantic import BaseModel


class AccountSummary(BaseModel):
    cash: Decimal = Decimal("0")
    total_value: Decimal = Decimal("0")
    realized_pnl: Decimal | None = None
    unrealized_pnl: Decimal = Decimal("0")
    daily_order_count: int = 0
    daily_loss_limit_reached: bool = False


class Position(BaseModel):
    symbol: str
    name: str = ""
    quantity: int
    average_price: Decimal
    current_price: Decimal
    evaluation_pnl: Decimal = Decimal("0")
    return_rate: Decimal = Decimal("0")

