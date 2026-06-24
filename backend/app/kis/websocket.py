import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime, timezone

import websockets

from app.kis.client import KISClient, KISConfigurationError


@dataclass(frozen=True)
class RealtimeTick:
    symbol: str
    price: int
    volume: int
    trade_strength: Decimal
    trading_halted: bool
    vi_reference_price: Decimal


@dataclass(frozen=True)
class OrderBookTick:
    symbol: str
    best_ask: Decimal
    best_bid: Decimal
    total_ask_quantity: int
    total_bid_quantity: int
    best_ask_quantity: int
    best_bid_quantity: int
    received_at: datetime


class KISWebSocketClient:
    def __init__(self, websocket_url: str, client: KISClient) -> None:
        self.websocket_url = websocket_url
        self.client = client
        self.connected = False

    async def stream_market(self, symbols: list[str]) -> AsyncIterator[RealtimeTick | OrderBookTick]:
        if not self.websocket_url or not symbols:
            raise KISConfigurationError("WebSocket URL and strategy symbols are required")
        approval = await self.client.post_public(
            "/oauth2/Approval",
            {
                "grant_type": "client_credentials",
                "appkey": self.client.app_key,
                "secretkey": self.client.app_secret,
            },
        )
        approval_key = str(approval.get("approval_key") or "")
        if not approval_key:
            raise KISConfigurationError("KIS WebSocket approval response is invalid")
        try:
            async with websockets.connect(self.websocket_url, ping_interval=20, ping_timeout=20) as socket:
                for symbol in symbols:
                    for tr_id in ("H0STCNT0", "H0STASP0"):
                        await socket.send(
                            json.dumps(
                                {
                                    "header": {
                                        "approval_key": approval_key,
                                        "custtype": "P",
                                        "tr_type": "1",
                                        "content-type": "utf-8",
                                    },
                                    "body": {"input": {"tr_id": tr_id, "tr_key": symbol}},
                                }
                            )
                        )
                        await asyncio.sleep(0.5)
                self.connected = True
                async for raw in socket:
                    if raw.startswith("{"):
                        payload = json.loads(raw)
                        if payload.get("header", {}).get("tr_id") == "PINGPONG":
                            await socket.pong(raw)
                        continue
                    parts = raw.split("|", 3)
                    if len(parts) != 4:
                        continue
                    fields = parts[3].split("^")
                    if parts[1] == "H0STCNT0" and len(fields) >= 19:
                        yield RealtimeTick(
                            symbol=fields[0],
                            price=int(fields[2]),
                            volume=int(fields[12]),
                            trade_strength=Decimal(fields[18] or "0"),
                            trading_halted=(fields[35] or "N") == "Y",
                            vi_reference_price=Decimal(fields[45] or "0") if len(fields) > 45 else Decimal("0"),
                        )
                    elif parts[1] == "H0STASP0" and len(fields) >= 45:
                        yield OrderBookTick(
                            symbol=fields[0],
                            best_ask=Decimal(fields[3] or "0"),
                            best_bid=Decimal(fields[13] or "0"),
                            total_ask_quantity=int(fields[43] or 0),
                            total_bid_quantity=int(fields[44] or 0),
                            best_ask_quantity=int(fields[23] or 0),
                            best_bid_quantity=int(fields[33] or 0),
                            received_at=datetime.now(timezone.utc),
                        )
        finally:
            self.connected = False
