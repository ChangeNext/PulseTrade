from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import Settings, TradingMode
from app.db.models import Base
from app.db.repository import TradingRepository
from app.notifications.base import Notifier
from app.schemas.order import ManualOrderRequest
from app.strategies.base import OrderBookSnapshot
from app.trading.execution_engine import ExecutionEngine
from app.trading.order_manager import OrderManager
from app.trading.order_supervisor import OrderSupervisor
from app.trading.risk_manager import RiskManager
from app.trading.sim_broker import SimBroker


class NullNotifier(Notifier):
    async def send(self, event: str, message: str) -> bool:
        return True


async def setup():
    db = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with db.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(db, expire_on_commit=False)
    settings = Settings(trading_mode=TradingMode.SIM, sim_latency_ms=0)
    engine = ExecutionEngine(
        settings, RiskManager(max_order_amount=Decimal("1000000")), OrderManager(), NullNotifier()
    )
    return db, sessions, settings, engine


@pytest.mark.asyncio
async def test_sim_broker_partial_fill_updates_position_and_costs() -> None:
    db, sessions, settings, engine = await setup()
    broker = SimBroker(settings, engine)
    book = OrderBookSnapshot(
        Decimal("70000"), Decimal("69900"), 100, 100, 1, 1, datetime.now(timezone.utc)
    )
    async with sessions() as session:
        repository = TradingRepository(session)
        response = await engine.submit_manual(
            ManualOrderRequest(symbol="005930", side="BUY", quantity=2, price=Decimal("70000")),
            repository,
            "sim-fill-001",
        )
        await broker.on_orderbook("005930", book, repository)
        order = await repository.get_order(response.order_id)
        assert order is not None and order.state == "PARTIALLY_FILLED"
        assert engine.context.position_quantities["005930"] == 1
        await broker.on_orderbook("005930", book, repository)
        assert order.state == "FILLED"
        assert order.commission > 0
        assert engine.context.position_quantities["005930"] == 2
    await db.dispose()


@pytest.mark.asyncio
async def test_supervisor_cancels_and_reprices_stale_sim_order() -> None:
    db, sessions, settings, engine = await setup()
    settings.strategy_order_ttl_seconds = 0
    supervisor = OrderSupervisor(settings, engine)
    book = OrderBookSnapshot(
        Decimal("70100"), Decimal("70000"), 100, 100, 10, 10, datetime.now(timezone.utc)
    )
    async with sessions() as session:
        repository = TradingRepository(session)
        await engine.submit_manual(
            ManualOrderRequest(symbol="005930", side="BUY", quantity=1, price=Decimal("70000")),
            repository,
            "sim-reprice-001",
            source="STRATEGY",
            strategy_name="TEST",
        )
        await supervisor.sweep("005930", book, repository)
        orders = await repository.recent_orders()
        assert len(orders) == 2
        replacement = next(order for order in orders if order.reprice_count == 1)
        original = next(order for order in orders if order.reprice_count == 0)
        assert replacement.price == Decimal("70100")
        assert original.state == "CANCELED"
    await db.dispose()
