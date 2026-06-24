import pytest

from app.trading.order_state import InvalidOrderTransition, OrderState, OrderStateMachine


def test_happy_path_to_filled() -> None:
    machine = OrderStateMachine()
    for state in (
        OrderState.RISK_CHECKED,
        OrderState.ORDER_REQUESTED,
        OrderState.ORDER_SENT,
        OrderState.PARTIALLY_FILLED,
        OrderState.FILLED,
    ):
        machine.transition_to(state)
    assert machine.state is OrderState.FILLED


def test_invalid_transition_is_rejected() -> None:
    machine = OrderStateMachine()
    with pytest.raises(InvalidOrderTransition):
        machine.transition_to(OrderState.FILLED)


def test_cancel_path() -> None:
    machine = OrderStateMachine(OrderState.ORDER_SENT)
    machine.transition_to(OrderState.CANCEL_REQUESTED)
    machine.transition_to(OrderState.CANCELED)
    assert machine.state is OrderState.CANCELED

