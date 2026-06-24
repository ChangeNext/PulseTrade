from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import Settings, TradingMode
from app.db.models import Base
from app.db.repository import TradingRepository
from app.notifications.base import Notifier
from app.schemas.order import ManualOrderRequest
from app.trading.execution_engine import ExecutionEngine, IdempotencyConflict
from app.trading.order_manager import OrderManager
from app.trading.risk_manager import RiskManager


class NullNotifier(Notifier):
    async def send(self, event: str, message: str) -> None:
        return None


@pytest.mark.asyncio
async def test_sim_order_is_idempotent() -> None:
    db = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with db.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(db, expire_on_commit=False)
    engine = ExecutionEngine(
        Settings(trading_mode=TradingMode.SIM), RiskManager(), OrderManager(), NullNotifier()
    )
    payload = ManualOrderRequest(symbol="005930", side="BUY", quantity=1, price=Decimal("70000"))
    async with sessions() as session:
        repository = TradingRepository(session)
        first = await engine.submit_manual(payload, repository, "request-0001")
        second = await engine.submit_manual(payload, repository, "request-0001")
        assert first.order_id == second.order_id
        assert first.state == "ORDER_SENT"
        assert len(await repository.recent_orders()) == 1
    await db.dispose()


@pytest.mark.asyncio
async def test_idempotency_key_rejects_different_payload() -> None:
    db = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with db.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(db, expire_on_commit=False)
    engine = ExecutionEngine(
        Settings(trading_mode=TradingMode.SIM), RiskManager(), OrderManager(), NullNotifier()
    )
    async with sessions() as session:
        repository = TradingRepository(session)
        await engine.submit_manual(
            ManualOrderRequest(symbol="005930", side="BUY", quantity=1, price=Decimal("70000")),
            repository,
            "request-0002",
        )
        with pytest.raises(IdempotencyConflict):
            await engine.submit_manual(
                ManualOrderRequest(symbol="005930", side="BUY", quantity=2, price=Decimal("70000")),
                repository,
                "request-0002",
            )
    await db.dispose()
