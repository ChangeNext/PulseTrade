from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import Settings, TradingMode
from app.db.models import Base, OrderRecord
from app.db.repository import TradingRepository
from app.kis.account import BrokerBalance, BrokerPosition
from app.kis.order import BrokerOrderSnapshot
from app.notifications.base import Notifier
from app.trading.execution_engine import ExecutionEngine
from app.trading.order_manager import OrderManager
from app.trading.reconciliation import ReconciliationService
from app.trading.risk_manager import RiskManager


class NullNotifier(Notifier):
    async def send(self, event: str, message: str) -> bool:
        return True


class FakeAccountService:
    async def synchronize(self) -> BrokerBalance:
        return BrokerBalance(
            cash=Decimal("500000"),
            total_value=Decimal("640000"),
            unrealized_pnl=Decimal("0"),
            positions=(
                BrokerPosition(
                    symbol="005930",
                    name="삼성전자",
                    quantity=2,
                    average_price=Decimal("70000"),
                    current_price=Decimal("70000"),
                    evaluation_amount=Decimal("140000"),
                    evaluation_pnl=Decimal("0"),
                    return_rate=Decimal("0"),
                ),
            ),
        )


class FakeOrderService:
    async def list_daily_orders(self) -> list[BrokerOrderSnapshot]:
        return [
            BrokerOrderSnapshot(
                broker_order_id="12345",
                broker_org_no="91234",
                symbol="005930",
                side="BUY",
                quantity=2,
                price=Decimal("70000"),
                filled_quantity=1,
                average_fill_price=Decimal("70000"),
                cancelable_quantity=1,
                state="PARTIALLY_FILLED",
                order_time="101500",
                order_date="20260624",
            )
        ]


class FakeMarketService:
    async def is_trading_day(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_reconciliation_attaches_ambiguous_submission_and_is_idempotent() -> None:
    db = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with db.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(db, expire_on_commit=False)
    engine = ExecutionEngine(
        Settings(trading_mode=TradingMode.PAPER), RiskManager(), OrderManager(), NullNotifier()
    )
    service = ReconciliationService(
        engine, FakeAccountService(), FakeOrderService(), FakeMarketService()
    )
    async with sessions() as session:
        repository = TradingRepository(session)
        await repository.add_order(
            OrderRecord(
                id="00000000-0000-0000-0000-000000000001",
                client_order_id="ambiguous-request",
                symbol="005930",
                side="BUY",
                quantity=2,
                price=Decimal("70000"),
                mode="PAPER",
                state="RECONCILING",
                message="unknown",
            )
        )
        await service.synchronize(repository)
        await service.synchronize(repository)
        orders = await repository.recent_orders()
        assert len(orders) == 1
        assert orders[0].broker_order_id == "12345"
        assert orders[0].filled_quantity == 1
        assert orders[0].state == "PARTIALLY_FILLED"
        assert engine.context.position_quantities["005930"] == 2
        assert engine.context.pending_symbols == {"005930"}
    await db.dispose()
