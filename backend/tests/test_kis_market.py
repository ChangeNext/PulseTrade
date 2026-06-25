import httpx
import pytest

from app.kis.auth import KISAuthService
from app.kis.client import KISClient
from app.kis.market import KISMarketService


@pytest.mark.asyncio
async def test_vi_status_is_active_until_cancel_time_is_present() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if request.url.path == "/oauth2/tokenP":
            return httpx.Response(200, json={"access_token": "token", "expires_in": 3600})
        assert request.headers["tr_id"] == "FHPST01390000"
        symbol = request.url.params["FID_INPUT_ISCD"]
        return httpx.Response(
            200,
            json={
                "rt_cd": "0",
                "output": [{
                    "mksc_shrn_iscd": symbol,
                    "bsop_date": request.url.params["FID_INPUT_DATE_1"],
                    "cntg_vi_hour": "101500",
                    "vi_cncl_hour": "",
                }],
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://openapi.koreainvestment.com:9443"
    ) as http_client:
        client = KISClient("https://openapi.koreainvestment.com:9443", "key", "secret", http_client=http_client)
        service = KISMarketService(client, KISAuthService(client))
        assert await service.is_vi_active("005930")
        assert await service.is_vi_active("005930")
    assert calls == 2


@pytest.mark.asyncio
async def test_period_bars_use_daily_chart_endpoint() -> None:
    requested_period = ""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requested_period
        if request.url.path == "/oauth2/tokenP":
            return httpx.Response(200, json={"access_token": "token", "expires_in": 3600})
        assert request.url.path == "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
        assert request.headers["tr_id"] == "FHKST03010100"
        requested_period = request.url.params["FID_PERIOD_DIV_CODE"]
        return httpx.Response(
            200,
            json={
                "rt_cd": "0",
                "output2": [
                    {
                        "stck_bsop_date": "20250110",
                        "stck_clpr": "71000",
                        "stck_hgpr": "72000",
                        "stck_lwpr": "70000",
                        "acml_vol": "1000",
                    },
                    {
                        "stck_bsop_date": "20250103",
                        "stck_clpr": "70000",
                        "stck_hgpr": "70500",
                        "stck_lwpr": "69000",
                        "acml_vol": "900",
                    },
                ],
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://openapi.koreainvestment.com:9443"
    ) as http_client:
        client = KISClient("https://openapi.koreainvestment.com:9443", "key", "secret", http_client=http_client)
        client._minimum_interval = 0
        service = KISMarketService(client, KISAuthService(client))
        bars = await service.get_period_bars("005930", "week")

    assert requested_period == "W"
    assert [bar.time for bar in bars] == ["20250103", "20250110"]
    assert bars[-1].price == 71000
