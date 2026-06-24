from dataclasses import dataclass

from app.kis.client import KISClient, KISConfigurationError
from app.trading.risk_manager import OrderIntent


@dataclass(frozen=True)
class BrokerOrderResult:
    broker_order_id: str
    accepted: bool
    message: str


class KISOrderService:
    def __init__(self, client: KISClient) -> None:
        self.client = client

    async def place_order(self, intent: OrderIntent) -> BrokerOrderResult:
        # TODO(KIS 공식 문서): 실전/모의 주문 endpoint, TR ID, hashkey 필요조건 검증 후 구현.
        raise KISConfigurationError("Order API requires official KIS documentation")

    async def get_order_status(self, broker_order_id: str) -> BrokerOrderResult:
        # TODO(KIS 공식 문서): 주문/체결 조회 endpoint, TR ID 및 페이징 검증 후 구현.
        raise KISConfigurationError("Order-status API requires official KIS documentation")

