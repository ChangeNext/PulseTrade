from decimal import Decimal

from app.strategies.base import ComponentSignal, SignalComponent, SignalContext


class OrderbookImbalanceStrategy(SignalComponent):
    name = "orderbook_imbalance"

    def evaluate(self, context: SignalContext) -> ComponentSignal:
        book = context.orderbook
        if book is None:
            return ComponentSignal(self.name, Decimal("0"), False, "Order book unavailable")
        total = book.total_bid_quantity + book.total_ask_quantity
        if total <= 0:
            return ComponentSignal(self.name, Decimal("0"), False, "Order book quantity is empty")
        imbalance = Decimal(book.total_bid_quantity - book.total_ask_quantity) / Decimal(total)
        return ComponentSignal(
            self.name,
            imbalance * Decimal("100"),
            True,
            f"Bid/ask imbalance is {imbalance:.3f}",
        )
