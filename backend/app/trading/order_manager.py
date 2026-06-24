from uuid import uuid4

from app.trading.order_state import OrderState, OrderStateMachine


class OrderManager:
    def __init__(self) -> None:
        self._orders: dict[str, OrderStateMachine] = {}

    def create(self) -> tuple[str, OrderState]:
        order_id = str(uuid4())
        machine = OrderStateMachine()
        self._orders[order_id] = machine
        return order_id, machine.state

    def transition(self, order_id: str, state: OrderState) -> OrderState:
        return self._orders[order_id].transition_to(state)

    def state(self, order_id: str) -> OrderState:
        return self._orders[order_id].state

