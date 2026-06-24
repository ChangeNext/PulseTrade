from dataclasses import dataclass
from decimal import Decimal

from app.kis.client import KISClient, KISConfigurationError


@dataclass(frozen=True)
class Quote:
    symbol: str
    price: Decimal
    volume: int


class KISMarketService:
    def __init__(self, client: KISClient) -> None:
        self.client = client

    async def get_current_price(self, symbol: str) -> Quote:
        # TODO(KIS 공식 문서): 국내주식 현재가 endpoint/TR ID/응답 매핑 검증 후 구현.
        raise KISConfigurationError("Current-price API requires official KIS documentation")

