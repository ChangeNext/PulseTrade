from decimal import Decimal

from app.trading.risk_manager import OrderIntent, RiskContext, RiskManager


def make_intent(amount_price: str = "50000") -> OrderIntent:
    return OrderIntent(symbol="005930", side="BUY", quantity=1, price=Decimal(amount_price))


def test_conservative_order_is_approved() -> None:
    decision = RiskManager().evaluate(make_intent(), RiskContext())
    assert decision.approved
    assert decision.reasons == ()


def test_order_amount_limit_blocks_order() -> None:
    decision = RiskManager(max_order_amount=Decimal("100000")).evaluate(
        make_intent("100001"), RiskContext()
    )
    assert not decision.approved
    assert "MAX_ORDER_AMOUNT_EXCEEDED" in decision.reasons


def test_pending_same_symbol_blocks_new_buy() -> None:
    context = RiskContext(pending_symbols={"005930"})
    decision = RiskManager().evaluate(make_intent(), context)
    assert not decision.approved
    assert "PENDING_ORDER_EXISTS" in decision.reasons


def test_disconnect_and_emergency_stop_block_order() -> None:
    context = RiskContext(api_connected=False, websocket_connected=False, emergency_stopped=True)
    decision = RiskManager().evaluate(make_intent(), context)
    assert set(decision.reasons) >= {
        "API_DISCONNECTED",
        "WEBSOCKET_DISCONNECTED",
        "EMERGENCY_STOPPED",
    }


def test_daily_limits_and_position_limit_block_order() -> None:
    context = RiskContext(
        daily_realized_pnl=Decimal("-50000"),
        daily_order_count=5,
        position_amounts={"005930": Decimal("280000")},
    )
    decision = RiskManager().evaluate(make_intent(), context)
    assert set(decision.reasons) >= {
        "MAX_DAILY_LOSS_REACHED",
        "MAX_DAILY_ORDERS_REACHED",
        "MAX_POSITION_AMOUNT_EXCEEDED",
    }


def test_sell_cannot_exceed_position_after_pending_sells() -> None:
    context = RiskContext(
        position_quantities={"005930": 3}, pending_sell_quantities={"005930": 2}
    )
    decision = RiskManager().evaluate(
        OrderIntent("005930", "SELL", 2, Decimal("50000")), context
    )
    assert "INSUFFICIENT_POSITION_QUANTITY" in decision.reasons


def test_invalid_tick_size_is_blocked() -> None:
    decision = RiskManager(max_order_amount=Decimal("1000000")).evaluate(
        OrderIntent("005930", "BUY", 1, Decimal("70001")), RiskContext()
    )
    assert "INVALID_TICK_SIZE" in decision.reasons


def test_unknown_daily_pnl_fails_closed() -> None:
    decision = RiskManager().evaluate(
        make_intent(), RiskContext(pnl_synchronized=False)
    )
    assert "DAILY_PNL_NOT_SYNCHRONIZED" in decision.reasons


def test_exit_sell_is_not_blocked_by_entry_limits() -> None:
    context = RiskContext(
        daily_realized_pnl=Decimal("-50000"),
        daily_order_count=5,
        position_quantities={"005930": 10},
    )
    decision = RiskManager(max_order_amount=Decimal("100000")).evaluate(
        OrderIntent("005930", "SELL", 10, Decimal("50000")), context
    )
    assert decision.approved
