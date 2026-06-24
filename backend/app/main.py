from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import OrderRecord
from app.db.repository import TradingRepository
from app.db.session import get_session, init_db
from app.kis.account import KISAccountService
from app.kis.auth import KISAuthService
from app.kis.client import KISAPIError, KISClient, KISConfigurationError
from app.notifications.telegram import TelegramNotifier
from app.schemas.account import AccountSummary, Position
from app.schemas.order import KillSwitchRequest, ManualOrderRequest, OrderResponse
from app.schemas.strategy import AutomationRequest, StrategyStatus
from app.trading.execution_engine import ExecutionEngine
from app.trading.order_manager import OrderManager
from app.trading.risk_manager import RiskManager
from app.utils.logger import configure_logging

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    await init_db()
    notifier = TelegramNotifier(settings.telegram_bot_token, settings.telegram_chat_id)
    risk_manager = RiskManager(
        max_order_amount=Decimal(settings.max_order_amount_krw),
        max_daily_loss=Decimal(settings.max_daily_loss_krw),
        max_daily_orders=settings.max_daily_orders,
        max_position_amount=Decimal(settings.max_position_amount_krw),
    )
    # 주문 서비스는 여전히 주입하지 않는다. 이번 연결은 계좌 읽기 전용이다.
    app.state.engine = ExecutionEngine(settings, risk_manager, OrderManager(), notifier)
    app.state.kis_client = None
    app.state.kis_account_service = None

    if settings.kis_configured:
        kis_client = KISClient(settings.kis_base_url, settings.kis_app_key, settings.kis_app_secret)
        app.state.kis_client = kis_client
        app.state.kis_account_service = KISAccountService(
            kis_client,
            KISAuthService(kis_client),
            settings.kis_account_number,
            settings.kis_account_product_code,
            paper="openapivts.koreainvestment.com" in settings.kis_base_url.lower(),
        )

    try:
        yield
    finally:
        if app.state.kis_client is not None:
            await app.state.kis_client.close()


app = FastAPI(title=settings.app_name, version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def engine_from(request: Request) -> ExecutionEngine:
    return request.app.state.engine


def account_service_from(request: Request) -> KISAccountService | None:
    return request.app.state.kis_account_service


def raise_kis_http_error(error: Exception) -> None:
    if isinstance(error, KISAPIError):
        raise HTTPException(
            status_code=502,
            detail={"code": error.code, "message": str(error)},
        ) from error
    raise HTTPException(
        status_code=503,
        detail={"code": "KIS_NOT_CONFIGURED", "message": str(error)},
    ) from error


@app.get("/api/health")
async def health(request: Request) -> dict:
    engine = engine_from(request)
    account_service = account_service_from(request)
    return {
        "status": "ok",
        "mode": settings.trading_mode,
        "live_enabled": settings.enable_live_trading,
        "kis_configured": settings.kis_configured,
        "kis_account_connected": bool(account_service and account_service.last_success_at is not None),
        "api_connected": engine.context.api_connected,
        "websocket_connected": engine.context.websocket_connected,
        "telegram_configured": bool(settings.telegram_bot_token and settings.telegram_chat_id),
        "emergency_stopped": engine.context.emergency_stopped,
    }


@app.get("/api/account", response_model=AccountSummary)
async def account_summary(request: Request) -> AccountSummary:
    service = account_service_from(request)
    if service is None:
        return AccountSummary()
    try:
        balance = await service.get_balance()
    except (KISAPIError, KISConfigurationError) as error:
        raise_kis_http_error(error)

    engine = engine_from(request)
    return AccountSummary(
        cash=balance.cash,
        total_value=balance.total_value,
        realized_pnl=None,  # 잔고조회 응답에는 당일 실현손익이 없다.
        unrealized_pnl=balance.unrealized_pnl,
        daily_order_count=engine.context.daily_order_count,
        daily_loss_limit_reached=(
            engine.context.daily_realized_pnl <= -engine.risk_manager.max_daily_loss
        ),
    )


@app.get("/api/positions", response_model=list[Position])
async def positions(request: Request) -> list[Position]:
    service = account_service_from(request)
    if service is None:
        return []
    try:
        balance = await service.get_balance()
    except (KISAPIError, KISConfigurationError) as error:
        raise_kis_http_error(error)
    return [
        Position(
            symbol=position.symbol,
            name=position.name,
            quantity=position.quantity,
            average_price=position.average_price,
            current_price=position.current_price,
            evaluation_pnl=position.evaluation_pnl,
            return_rate=position.return_rate,
        )
        for position in balance.positions
    ]


@app.get("/api/orders")
async def recent_orders(session: SessionDep) -> list[dict]:
    records = await TradingRepository(session).recent_orders()
    return [
        {
            "id": row.id,
            "symbol": row.symbol,
            "side": row.side,
            "quantity": row.quantity,
            "price": row.price,
            "mode": row.mode,
            "state": row.state,
            "message": row.message,
            "created_at": row.created_at,
        }
        for row in records
    ]


@app.post("/api/orders/manual", response_model=OrderResponse)
async def manual_order(payload: ManualOrderRequest, request: Request, session: SessionDep) -> OrderResponse:
    engine = engine_from(request)
    result = await engine.submit_manual(payload)
    repository = TradingRepository(session)
    await repository.add_order(
        OrderRecord(
            id=result.order_id,
            symbol=payload.symbol,
            side=payload.side,
            quantity=payload.quantity,
            price=payload.price,
            mode=result.mode,
            state=result.state,
            message=result.message,
        )
    )
    await repository.add_event(
        "RISK_BLOCK" if result.risk_reasons else "ORDER_REQUEST",
        result.message,
        {"order_id": result.order_id, "risk_reasons": result.risk_reasons},
    )
    return result


@app.post("/api/control/kill-switch")
async def kill_switch(payload: KillSwitchRequest, request: Request) -> dict:
    engine = engine_from(request)
    await engine.set_emergency_stop(payload.stopped)
    return {"emergency_stopped": engine.context.emergency_stopped}


@app.post("/api/control/automation")
async def automation(payload: AutomationRequest, request: Request) -> dict:
    engine = engine_from(request)
    if payload.enabled and engine.context.emergency_stopped:
        return {"enabled": False, "message": "Emergency stop must be cleared first"}
    engine.automation_enabled = payload.enabled
    return {"enabled": engine.automation_enabled}


@app.get("/api/strategy", response_model=StrategyStatus)
async def strategy_status(request: Request) -> StrategyStatus:
    engine = engine_from(request)
    return StrategyStatus(
        name="ORB_VWAP_VOLUME",
        enabled=engine.automation_enabled,
        signal_only=True,
        status="RUNNING" if engine.automation_enabled else "IDLE",
    )

