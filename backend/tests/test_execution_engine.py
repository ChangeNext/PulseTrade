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


class FakeBrokerOrderService:
    def __init__(self) -> None:
        self.placed = False

    async def get_orderable_cash(self, intent) -> Decimal:
        return Decimal("1000000")

    async def place_order(self, intent):
        self.placed = True

        class Result:
            broker_order_id = "12345"
            broker_org_no = "91234"
            message = "accepted"

        return Result()


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
async def test_live_order_requires_enable_flag_before_broker_call() -> None:
    db = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with db.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(db, expire_on_commit=False)
    broker = FakeBrokerOrderService()
    engine = ExecutionEngine(
        Settings(
            trading_mode=TradingMode.LIVE,
            enable_live_trading=False,
            kis_base_url="https://openapi.koreainvestment.com:9443",
        ),
        RiskManager(max_order_amount=Decimal("1000000")),
        OrderManager(),
        NullNotifier(),
        broker,
    )
    async with sessions() as session:
        result = await engine.submit_manual(
            ManualOrderRequest(
                symbol="005930",
                side="BUY",
                quantity=1,
                price=Decimal("70000"),
                live_confirmation="I_UNDERSTAND_LIVE_TRADING_RISK",
            ),
            TradingRepository(session),
            "live-request-0001",
        )
    assert result.state == "REJECTED"
    assert result.risk_reasons == ["LIVE_TRADING_DISABLED"]
    assert broker.placed is False
    await db.dispose()


@pytest.mark.asyncio
async def test_live_order_requires_exact_confirmation() -> None:
    db = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with db.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(db, expire_on_commit=False)
    broker = FakeBrokerOrderService()
    engine = ExecutionEngine(
        Settings(
            trading_mode=TradingMode.LIVE,
            enable_live_trading=True,
            kis_base_url="https://openapi.koreainvestment.com:9443",
        ),
        RiskManager(max_order_amount=Decimal("1000000")),
        OrderManager(),
        NullNotifier(),
        broker,
    )
    async with sessions() as session:
        result = await engine.submit_manual(
            ManualOrderRequest(symbol="005930", side="BUY", quantity=1, price=Decimal("70000")),
            TradingRepository(session),
            "live-request-0002",
        )
    assert result.state == "REJECTED"
    assert result.risk_reasons == ["LIVE_CONFIRMATION_REQUIRED"]
    assert broker.placed is False
    await db.dispose()


@pytest.mark.asyncio
async def test_live_order_routes_only_after_all_preconditions() -> None:
    db = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with db.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(db, expire_on_commit=False)
    broker = FakeBrokerOrderService()
    engine = ExecutionEngine(
        Settings(
            trading_mode=TradingMode.LIVE,
            enable_live_trading=True,
            kis_base_url="https://openapi.koreainvestment.com:9443",
        ),
        RiskManager(max_order_amount=Decimal("1000000")),
        OrderManager(),
        NullNotifier(),
        broker,
    )
    engine.context.api_connected = True
    engine.context.websocket_connected = True
    engine.context.account_synchronized = True
    engine.context.orders_synchronized = True
    async with sessions() as session:
        result = await engine.submit_manual(
            ManualOrderRequest(
                symbol="005930",
                side="BUY",
                quantity=1,
                price=Decimal("70000"),
                live_confirmation="I_UNDERSTAND_LIVE_TRADING_RISK",
            ),
            TradingRepository(session),
            "live-request-0003",
        )
    assert result.state == "ORDER_SENT"
    assert result.broker_order_id == "12345"
    assert broker.placed is True
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
