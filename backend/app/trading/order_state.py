from enum import StrEnum


class OrderState(StrEnum):
    SIGNAL = "SIGNAL"
    RISK_CHECKED = "RISK_CHECKED"
    ORDER_REQUESTED = "ORDER_REQUESTED"
    ORDER_SENT = "ORDER_SENT"
    RECONCILING = "RECONCILING"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    ERROR = "ERROR"


ALLOWED_TRANSITIONS: dict[OrderState, set[OrderState]] = {
    OrderState.SIGNAL: {OrderState.RISK_CHECKED, OrderState.REJECTED, OrderState.ERROR},
    OrderState.RISK_CHECKED: {OrderState.ORDER_REQUESTED, OrderState.REJECTED, OrderState.ERROR},
    OrderState.ORDER_REQUESTED: {
        OrderState.ORDER_SENT,
        OrderState.RECONCILING,
        OrderState.REJECTED,
        OrderState.ERROR,
    },
    OrderState.RECONCILING: {
        OrderState.ORDER_SENT,
        OrderState.PARTIALLY_FILLED,
        OrderState.FILLED,
        OrderState.REJECTED,
        OrderState.ERROR,
    },
    OrderState.ORDER_SENT: {
        OrderState.PARTIALLY_FILLED,
        OrderState.FILLED,
        OrderState.CANCEL_REQUESTED,
        OrderState.REJECTED,
        OrderState.ERROR,
    },
    OrderState.PARTIALLY_FILLED: {
        OrderState.FILLED,
        OrderState.CANCEL_REQUESTED,
        OrderState.ERROR,
    },
    OrderState.CANCEL_REQUESTED: {OrderState.CANCELED, OrderState.FILLED, OrderState.ERROR},
    OrderState.FILLED: set(),
    OrderState.CANCELED: set(),
    OrderState.REJECTED: set(),
    OrderState.ERROR: set(),
}


class InvalidOrderTransition(ValueError):
    pass


class OrderStateMachine:
    def __init__(self, state: OrderState = OrderState.SIGNAL) -> None:
        self.state = state

    def transition_to(self, next_state: OrderState) -> OrderState:
        if next_state not in ALLOWED_TRANSITIONS[self.state]:
            raise InvalidOrderTransition(f"{self.state} -> {next_state} transition is not allowed")
        self.state = next_state
        return self.state
