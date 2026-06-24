from collections.abc import AsyncIterator
from dataclasses import dataclass

from app.kis.client import KISConfigurationError


@dataclass(frozen=True)
class RealtimeTick:
    symbol: str
    price: int
    volume: int


class KISWebSocketClient:
    def __init__(self, websocket_url: str) -> None:
        self.websocket_url = websocket_url
        self.connected = False

    async def stream_quotes(self, symbols: list[str]) -> AsyncIterator[RealtimeTick]:
        # TODO(KIS 공식 문서): approval key, 구독 TR ID, ping/pong 및 메시지 파싱 검증 후 구현.
        raise KISConfigurationError("WebSocket protocol requires official KIS documentation")
        yield  # pragma: no cover - AsyncIterator 타입 유지를 위한 unreachable 코드

