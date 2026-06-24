from decimal import Decimal

import httpx
import pytest

from app.kis.auth import KISAuthService
from app.kis.client import KISClient
from app.kis.order import KISOrderService
from app.trading.risk_manager import OrderIntent


@pytest.mark.asyncio
async def test_paper_limit_buy_uses_official_contract() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/oauth2/tokenP":
            return httpx.Response(200, json={"access_token": "token", "expires_in": 3600})
        assert request.url.path.endswith("/order-cash")
        assert request.headers["tr_id"] == "VTTC0012U"
        payload = __import__("json").loads(request.content)
        assert payload["ORD_DVSN"] == "00"
        assert payload["ORD_QTY"] == "1"
        assert payload["ORD_UNPR"] == "70000"
        return httpx.Response(
            200,
            json={
                "rt_cd": "0",
                "msg1": "정상처리",
                "output": {"ODNO": "12345", "KRX_FWDG_ORD_ORGNO": "91234"},
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://openapivts.koreainvestment.com:29443"
    ) as http_client:
        client = KISClient("https://openapivts.koreainvestment.com:29443", "key", "secret", http_client=http_client)
        service = KISOrderService(client, KISAuthService(client), "12345678", "01", paper=True)
        result = await service.place_order(
            OrderIntent("005930", "BUY", 1, Decimal("70000"))
        )
    assert result.broker_order_id == "12345"
    assert len(requests) == 2


@pytest.mark.asyncio
async def test_daily_order_maps_partial_fill() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth2/tokenP":
            return httpx.Response(200, json={"access_token": "token", "expires_in": 3600})
        assert request.headers["tr_id"] == "VTTC0081R"
        return httpx.Response(
            200,
            headers={"tr_cont": ""},
            json={
                "rt_cd": "0",
                "output1": [{
                    "odno": "12345", "ord_gno_brno": "91234", "pdno": "005930",
                    "sll_buy_dvsn_cd": "02", "ord_qty": "3", "ord_unpr": "70000",
                    "tot_ccld_qty": "1", "avg_prvs": "69900", "psbl_qty": "2",
                    "ord_dt": "20260624", "ord_tmd": "101500",
                }],
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://openapivts.koreainvestment.com:29443"
    ) as http_client:
        client = KISClient("https://openapivts.koreainvestment.com:29443", "key", "secret", http_client=http_client)
        service = KISOrderService(client, KISAuthService(client), "12345678", "01", paper=True)
        rows = await service.list_daily_orders()
    assert rows[0].state == "PARTIALLY_FILLED"
    assert rows[0].filled_quantity == 1
    assert rows[0].average_fill_price == Decimal("69900")
