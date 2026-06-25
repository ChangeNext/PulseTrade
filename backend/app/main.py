import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import TradingMode, get_settings
from app.db.repository import TradingRepository
from app.db.session import AsyncSessionFactory, get_session, init_db
from app.kis.account import KISAccountService
from app.kis.auth import KISAuthService
from app.kis.client import KISAPIError, KISClient, KISConfigurationError
from app.kis.market import KISMarketService
from app.kis.order import KISOrderService
from app.kis.websocket import KISWebSocketClient
from app.notifications.telegram import TelegramNotifier
from app.schemas.account import AccountSummary, Position
from app.schemas.market import MarketBar, MarketQuote
from app.schemas.order import CancelOrderResponse, KillSwitchRequest, ManualOrderRequest, OrderResponse
from app.schemas.strategy import AutomationRequest, StrategyStatus
from app.strategies.runtime import StrategyRuntime
from app.trading.execution_engine import ExecutionEngine, IdempotencyConflict
from app.trading.order_manager import OrderManager
from app.trading.reconciliation import ReconciliationService
from app.trading.risk_manager import RiskManager
from app.trading.sim_broker import SimBroker
from app.utils.logger import configure_logging

settings = get_settings()
KST = timezone(timedelta(hours=9))


def market_is_open() -> bool:
    now = datetime.now(KST)
    return now.weekday() < 5 and time(9, 0) <= now.time() <= time(15, 30)


async def reconciliation_loop(app: FastAPI) -> None:
    while True:
        await asyncio.sleep(max(settings.order_reconcile_interval_seconds, 15.0))
        service: ReconciliationService | None = app.state.reconciliation
        if service is None:
            continue
        try:
            async with AsyncSessionFactory() as session:
                await service.synchronize(TradingRepository(session))
        except asyncio.CancelledError:
            raise
        except Exception:
            app.state.engine.refresh_effective_automation(False)
        else:
            strategy = app.state.strategy_runtime
            app.state.engine.refresh_effective_automation(bool(strategy and strategy.ready))


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
    app.state.kis_client = None
    app.state.kis_account_service = None
    app.state.kis_order_service = None
    app.state.reconciliation = None
    app.state.strategy_runtime = None
    app.state.market_service = None
    app.state.sim_broker = None
    tasks: list[asyncio.Task] = []

    kis_client = None
    auth = None
    if settings.kis_configured:
        if settings.trading_mode == TradingMode.PAPER and not settings.kis_is_paper:
            raise RuntimeError("PAPER mode requires KIS paper base URL")
        if settings.trading_mode == TradingMode.LIVE and not settings.kis_is_live:
            raise RuntimeError("LIVE mode requires KIS live base URL")
        kis_client = KISClient(settings.kis_base_url, settings.kis_app_key, settings.kis_app_secret)
        auth = KISAuthService(kis_client)
        app.state.kis_client = kis_client
        app.state.kis_account_service = KISAccountService(
            kis_client,
            auth,
            settings.kis_account_number,
            settings.kis_account_product_code,
            paper=settings.kis_is_paper,
        )
        app.state.market_service = KISMarketService(kis_client, auth)

    order_service = None
    if (
        settings.trading_mode in {TradingMode.PAPER, TradingMode.LIVE}
        and kis_client is not None
        and auth is not None
        and (settings.trading_mode != TradingMode.LIVE or settings.enable_live_trading)
    ):
        order_service = KISOrderService(
            kis_client,
            auth,
            settings.kis_account_number,
            settings.kis_account_product_code,
            paper=settings.trading_mode == TradingMode.PAPER,
        )
        app.state.kis_order_service = order_service

    app.state.engine = ExecutionEngine(
        settings, risk_manager, OrderManager(), notifier, order_service
    )
    app.state.engine.context.market_open = (
        True if settings.trading_mode == TradingMode.SIM else market_is_open()
    )

    async with AsyncSessionFactory() as session:
        repository = TradingRepository(session)
        app.state.engine.context.emergency_stopped = (
            await repository.get_runtime_state("emergency_stopped", "false") == "true"
        )
        app.state.engine.automation_desired = (
            await repository.get_runtime_state("automation_desired", "false") == "true"
        )

    if settings.trading_mode == TradingMode.SIM:
        app.state.sim_broker = SimBroker(settings, app.state.engine)
        async with AsyncSessionFactory() as session:
            await app.state.sim_broker.restore(TradingRepository(session))

    if order_service is not None and app.state.kis_account_service is not None:
        app.state.reconciliation = ReconciliationService(
            app.state.engine,
            app.state.kis_account_service,
            order_service,
            app.state.market_service,
        )
        try:
            async with AsyncSessionFactory() as session:
                await asyncio.wait_for(
                    app.state.reconciliation.synchronize(TradingRepository(session)),
                    timeout=8,
                )
        except Exception:
            pass
        tasks.append(asyncio.create_task(reconciliation_loop(app)))

    if (
        kis_client is not None
        and auth is not None
        and settings.kis_websocket_url
        and settings.strategy_symbol_list
    ):
        app.state.strategy_runtime = StrategyRuntime(
            settings,
            app.state.engine,
            app.state.market_service,
            KISWebSocketClient(settings.kis_websocket_url, kis_client),
            app.state.sim_broker,
        )
        tasks.append(asyncio.create_task(app.state.strategy_runtime.run()))

    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        if kis_client is not None:
            await kis_client.close()


app = FastAPI(title=settings.app_name, version="0.3.0", lifespan=lifespan)
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


def market_service_from(request: Request) -> KISMarketService | None:
    return request.app.state.market_service


def raise_kis_http_error(error: Exception) -> None:
    if isinstance(error, KISAPIError):
        raise HTTPException(
            status_code=502, detail={"code": error.code, "message": str(error)}
        ) from error
    raise HTTPException(
        status_code=503,
        detail={"code": "KIS_NOT_CONFIGURED", "message": str(error)},
    ) from error


@app.get("/api/health")
async def health(request: Request) -> dict:
    engine = engine_from(request)
    strategy = request.app.state.strategy_runtime
    reconciliation = request.app.state.reconciliation
    return {
        "status": "ok",
        "mode": settings.trading_mode,
        "live_enabled": bool(
            settings.trading_mode == TradingMode.LIVE
            and settings.enable_live_trading
            and request.app.state.kis_order_service is not None
        ),
        "kis_configured": settings.kis_configured,
        "rest_connected": bool(
            account_service_from(request)
            and account_service_from(request).last_success_at is not None
        ),
        "kis_account_connected": bool(
            account_service_from(request)
            and account_service_from(request).last_success_at is not None
        ),
        "api_connected": engine.context.api_connected,
        "websocket_connected": engine.context.websocket_connected,
        "account_synced": engine.context.account_synchronized,
        "orders_synced": engine.context.orders_synchronized,
        "pnl_synced": engine.context.pnl_synchronized,
        "strategy_ready": bool(strategy and strategy.ready),
        "strategy_error": strategy.last_error if strategy else "Strategy runtime is not configured",
        "reconciliation_error": reconciliation.last_error if reconciliation else None,
        "automation_desired": engine.automation_desired,
        "automation_effective": engine.automation_enabled,
        "telegram_configured": bool(settings.telegram_bot_token and settings.telegram_chat_id),
        "emergency_stopped": engine.context.emergency_stopped,
    }


@app.get("/api/account", response_model=AccountSummary)
async def account_summary(request: Request) -> AccountSummary:
    engine = engine_from(request)
    if settings.trading_mode == TradingMode.SIM:
        position_value = sum(engine.context.position_amounts.values(), Decimal("0"))
        cost_value = sum(
            engine.context.position_average_prices.get(symbol, Decimal("0")) * quantity
            for symbol, quantity in engine.context.position_quantities.items()
        )
        unrealized = position_value - cost_value
        cash = engine.context.available_cash or Decimal("0")
        return AccountSummary(
            cash=cash,
            total_value=cash + position_value,
            realized_pnl=engine.context.daily_realized_pnl,
            unrealized_pnl=unrealized,
            daily_order_count=engine.context.daily_order_count,
            daily_loss_limit_reached=(
                engine.context.daily_realized_pnl <= -engine.risk_manager.max_daily_loss
            ),
        )
    service = account_service_from(request)
    if service is None:
        return AccountSummary()
    try:
        balance = await service.get_balance()
    except (KISAPIError, KISConfigurationError) as error:
        raise_kis_http_error(error)
    return AccountSummary(
        cash=balance.cash,
        total_value=balance.total_value,
        realized_pnl=(engine.context.daily_realized_pnl if engine.context.pnl_synchronized else None),
        unrealized_pnl=balance.unrealized_pnl,
        daily_order_count=engine.context.daily_order_count,
        daily_loss_limit_reached=(
            engine.context.daily_realized_pnl <= -engine.risk_manager.max_daily_loss
        ),
    )


@app.get("/api/positions", response_model=list[Position])
async def positions(request: Request) -> list[Position]:
    engine = engine_from(request)
    if settings.trading_mode == TradingMode.SIM:
        result: list[Position] = []
        for symbol, quantity in engine.context.position_quantities.items():
            if quantity <= 0:
                continue
            average = engine.context.position_average_prices.get(symbol, Decimal("0"))
            current = engine.context.position_current_prices.get(symbol, average)
            pnl = (current - average) * quantity
            result.append(
                Position(
                    symbol=symbol,
                    name=f"SIM {symbol}",
                    quantity=quantity,
                    average_price=average,
                    current_price=current,
                    evaluation_pnl=pnl,
                    return_rate=(current - average) / average * 100 if average > 0 else Decimal("0"),
                )
            )
        return result
    service = account_service_from(request)
    if service is None:
        return []
    try:
        balance = await service.get_balance()
    except (KISAPIError, KISConfigurationError) as error:
        raise_kis_http_error(error)
    return [
        Position(
            symbol=row.symbol,
            name=row.name,
            quantity=row.quantity,
            average_price=row.average_price,
            current_price=row.current_price,
            evaluation_pnl=row.evaluation_pnl,
            return_rate=row.return_rate,
        )
        for row in balance.positions
    ]


@app.get("/api/market/{symbol}", response_model=MarketQuote)
async def market_quote(symbol: str, request: Request) -> MarketQuote:
    if not symbol.isdigit() or len(symbol) != 6:
        raise HTTPException(status_code=422, detail="Symbol must be a 6-digit stock code")
    service = market_service_from(request)
    if service is None:
        raise HTTPException(status_code=503, detail="KIS market service is not configured")
    try:
        quote = await service.get_current_price(symbol)
    except (KISAPIError, KISConfigurationError) as error:
        raise_kis_http_error(error)
    return MarketQuote(
        symbol=quote.symbol,
        name=quote.name,
        price=quote.price,
        volume=quote.volume,
    )


@app.get("/api/market/{symbol}/bars", response_model=list[MarketBar])
async def market_bars(symbol: str, request: Request, period: str = "1m") -> list[MarketBar]:
    if not symbol.isdigit() or len(symbol) != 6:
        raise HTTPException(status_code=422, detail="Symbol must be a 6-digit stock code")
    if period not in {"1m", "day", "week", "month"}:
        raise HTTPException(status_code=422, detail="Unsupported chart period")
    service = market_service_from(request)
    if service is None:
        raise HTTPException(status_code=503, detail="KIS market service is not configured")
    try:
        bars = (
            await service.get_minute_bars(symbol, max_pages=1)
            if period == "1m"
            else await service.get_period_bars(symbol, period)
        )
    except (KISAPIError, KISConfigurationError) as error:
        raise_kis_http_error(error)
    return [
        MarketBar(
            time=bar.time,
            price=bar.price,
            high=bar.high,
            low=bar.low,
            volume=bar.volume,
        )
        for bar in bars
    ]


@app.get("/api/orders")
async def recent_orders(session: SessionDep) -> list[dict]:
    records = await TradingRepository(session).recent_orders()
    return [
        {
            "id": row.id,
            "client_order_id": row.client_order_id,
            "broker_order_id": row.broker_order_id,
            "symbol": row.symbol,
            "side": row.side,
            "quantity": row.quantity,
            "price": row.price,
            "filled_quantity": row.filled_quantity,
            "average_fill_price": row.average_fill_price,
            "source": row.source,
            "commission": row.commission,
            "tax": row.tax,
            "reprice_count": row.reprice_count,
            "mode": row.mode,
            "state": row.state,
            "message": row.message,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
        for row in records
    ]


@app.post("/api/orders/manual", response_model=OrderResponse)
async def manual_order(
    payload: ManualOrderRequest,
    request: Request,
    session: SessionDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=64)],
) -> OrderResponse:
    try:
        return await engine_from(request).submit_manual(
            payload, TradingRepository(session), idempotency_key
        )
    except IdempotencyConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/orders/{order_id}/cancel", response_model=CancelOrderResponse)
async def cancel_order(order_id: str, request: Request, session: SessionDep) -> CancelOrderResponse:
    try:
        return await engine_from(request).cancel_order(order_id, TradingRepository(session))
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Order not found") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/control/reconcile")
async def reconcile(request: Request, session: SessionDep) -> dict:
    service = request.app.state.reconciliation
    if service is None:
        raise HTTPException(status_code=503, detail="Broker reconciliation is not configured")
    try:
        result = await service.synchronize(TradingRepository(session))
    except Exception as error:
        raise_kis_http_error(error)
    strategy = request.app.state.strategy_runtime
    engine_from(request).refresh_effective_automation(bool(strategy and strategy.ready))
    return result


@app.post("/api/control/kill-switch")
async def kill_switch(payload: KillSwitchRequest, request: Request, session: SessionDep) -> dict:
    await engine_from(request).set_emergency_stop(payload.stopped, TradingRepository(session))
    return {"emergency_stopped": engine_from(request).context.emergency_stopped}


@app.post("/api/control/automation")
async def automation(payload: AutomationRequest, request: Request, session: SessionDep) -> dict:
    engine = engine_from(request)
    if settings.trading_mode == TradingMode.LIVE and payload.enabled:
        engine.automation_desired = False
        await TradingRepository(session).set_runtime_state("automation_desired", "false")
        return {
            "enabled": False,
            "desired": False,
            "message": "LIVE automation is disabled until a separate live strategy release",
        }
    if payload.enabled and engine.context.emergency_stopped:
        return {
            "enabled": False,
            "desired": engine.automation_desired,
            "message": "Emergency stop must be cleared first",
        }
    engine.automation_desired = payload.enabled
    await TradingRepository(session).set_runtime_state(
        "automation_desired", "true" if payload.enabled else "false"
    )
    strategy = request.app.state.strategy_runtime
    effective = engine.refresh_effective_automation(bool(strategy and strategy.ready))
    return {
        "enabled": effective,
        "desired": engine.automation_desired,
        "message": None if effective or not payload.enabled else "Waiting for broker and strategy readiness",
    }


@app.get("/api/strategy", response_model=StrategyStatus)
async def strategy_status(request: Request) -> StrategyStatus:
    engine = engine_from(request)
    runtime = request.app.state.strategy_runtime
    return StrategyStatus(
        name="SIGNAL_SCORER",
        enabled=engine.automation_enabled,
        signal_only=not engine.automation_desired,
        status="RUNNING" if engine.automation_enabled else "WAITING" if engine.automation_desired else "IDLE",
        auto_order_enabled=engine.automation_enabled,
        desired_enabled=engine.automation_desired,
        ready=bool(runtime and runtime.ready),
        readiness_reason=runtime.last_error if runtime else "Strategy runtime is not configured",
        watched_symbols=runtime.symbols if runtime else settings.strategy_symbol_list,
        signals=runtime.signal_payloads() if runtime else [],
    )
