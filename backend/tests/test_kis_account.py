from decimal import Decimal
import asyncio

import httpx
import pytest

from app.kis.account import KISAccountService
from app.kis.auth import KISAuthService
from app.kis.client import KISClient


def test_real_account_balance_is_mapped_and_cached() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path == "/oauth2/tokenP":
            return httpx.Response(
                200,
                json={
                    "access_token": "test-token",
                    "access_token_token_expired": "2099-12-31 23:59:59",
                },
            )
        assert request.headers["tr_id"] == "TTTC8434R"
        assert request.headers["custtype"] == "P"
        assert request.url.params["CANO"] == "12345678"
        assert request.url.params["ACNT_PRDT_CD"] == "01"
        return httpx.Response(
            200,
            headers={"tr_cont": ""},
            json={
                "rt_cd": "0",
                "msg_cd": "MCA00000",
                "msg1": "정상처리 되었습니다.",
                "output1": [
                    {
                        "pdno": "005930",
                        "prdt_name": "삼성전자",
                        "hldg_qty": "2",
                        "pchs_avg_pric": "70000.0000",
                        "prpr": "71000",
                        "evlu_amt": "142000",
                        "evlu_pfls_amt": "2000",
                        "evlu_pfls_rt": "1.42857143",
                    }
                ],
                "output2": [
                    {
                        "dnca_tot_amt": "10000",
                        "tot_evlu_amt": "152000",
                        "evlu_pfls_smtl_amt": "2000",
                    }
                ],
                "ctx_area_fk100": "",
                "ctx_area_nk100": "",
            },
        )

    async def run_test():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://openapi.koreainvestment.com:9443",
        ) as http_client:
            client = KISClient("https://openapi.koreainvestment.com:9443", "key", "secret", http_client=http_client)
            service = KISAccountService(client, KISAuthService(client), "12345678", "01")
            balance = await service.get_balance()
            cached = await service.get_balance()
            return balance, cached

    balance, cached = asyncio.run(run_test())

    assert balance is cached
    assert balance.cash == Decimal("10000")
    assert balance.total_value == Decimal("152000")
    assert balance.unrealized_pnl == Decimal("2000")
    assert len(balance.positions) == 1
    assert balance.positions[0].symbol == "005930"
    assert balance.positions[0].quantity == 2
    assert len(calls) == 2


def test_account_number_requires_first_eight_digits() -> None:
    client = KISClient("https://example.com", "key", "secret")
    with pytest.raises(ValueError, match="first 8 digits"):
        KISAccountService(client, KISAuthService(client), "1234-5678", "01")
