import asyncio
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from time import monotonic
from typing import Any

from app.kis.auth import KISAuthService
from app.kis.client import KISClient, KISConfigurationError

BALANCE_PATH = "/uapi/domestic-stock/v1/trading/inquire-balance"
REAL_BALANCE_TR_ID = "TTTC8434R"
PAPER_BALANCE_TR_ID = "VTTC8434R"


@dataclass(frozen=True)
class BrokerPosition:
    symbol: str
    name: str
    quantity: int
    average_price: Decimal
    current_price: Decimal
    evaluation_amount: Decimal
    evaluation_pnl: Decimal
    return_rate: Decimal


@dataclass(frozen=True)
class BrokerBalance:
    cash: Decimal
    total_value: Decimal
    unrealized_pnl: Decimal
    positions: tuple[BrokerPosition, ...]


class KISAccountService:
    """공식 국내주식 잔고조회 API를 사용하는 읽기 전용 계좌 서비스."""

    def __init__(
        self,
        client: KISClient,
        auth: KISAuthService,
        account_number: str,
        product_code: str,
        *,
        paper: bool = False,
        cache_seconds: float = 3.0,
    ) -> None:
        if not account_number.isdigit() or len(account_number) != 8:
            raise KISConfigurationError("KIS account number must be the first 8 digits")
        if not product_code.isdigit() or len(product_code) != 2:
            raise KISConfigurationError("KIS account product code must be 2 digits")
        self.client = client
        self.auth = auth
        self.account_number = account_number
        self.product_code = product_code
        self.paper = paper
        self.cache_seconds = cache_seconds
        self._cache: BrokerBalance | None = None
        self._cached_at = 0.0
        self._lock = asyncio.Lock()
        self.last_success_at: float | None = None

    async def get_balance(self, *, force: bool = False) -> BrokerBalance:
        if not force and self._cache is not None and monotonic() - self._cached_at < self.cache_seconds:
            return self._cache
        async with self._lock:
            if not force and self._cache is not None and monotonic() - self._cached_at < self.cache_seconds:
                return self._cache
            await self.auth.ensure_access_token()
            balance = await self._fetch_all_pages()
            self._cache = balance
            self._cached_at = monotonic()
            self.last_success_at = self._cached_at
            return balance

    async def _fetch_all_pages(self) -> BrokerBalance:
        positions: list[BrokerPosition] = []
        summary: dict[str, Any] = {}
        fk100 = ""
        nk100 = ""
        tr_cont = ""
        tr_id = PAPER_BALANCE_TR_ID if self.paper else REAL_BALANCE_TR_ID

        for _ in range(10):
            response = await self.client.request_response(
                "GET",
                BALANCE_PATH,
                tr_id=tr_id,
                tr_cont=tr_cont,
                params={
                    "CANO": self.account_number,
                    "ACNT_PRDT_CD": self.product_code,
                    "AFHR_FLPR_YN": "N",
                    "OFL_YN": "",
                    "INQR_DVSN": "02",
                    "UNPR_DVSN": "01",
                    "FUND_STTL_ICLD_YN": "N",
                    "FNCG_AMT_AUTO_RDPT_YN": "N",
                    "PRCS_DVSN": "00",
                    "CTX_AREA_FK100": fk100,
                    "CTX_AREA_NK100": nk100,
                },
            )
            body = response.data
            rows = body.get("output1") or []
            if isinstance(rows, dict):
                rows = [rows]
            positions.extend(self._parse_position(row) for row in rows if self._decimal(row.get("hldg_qty")) > 0)

            output2 = body.get("output2") or []
            if isinstance(output2, list) and output2:
                summary = output2[0]
            elif isinstance(output2, dict):
                summary = output2

            next_page = response.headers.get("tr_cont", "")
            if next_page not in {"M", "F"}:
                break
            fk100 = str(body.get("ctx_area_fk100") or "")
            nk100 = str(body.get("ctx_area_nk100") or "")
            tr_cont = "N"
            await asyncio.sleep(0.05 if not self.paper else 0.5)

        return BrokerBalance(
            cash=self._decimal(summary.get("dnca_tot_amt")),
            total_value=self._decimal(summary.get("tot_evlu_amt")),
            unrealized_pnl=self._decimal(summary.get("evlu_pfls_smtl_amt")),
            positions=tuple(positions),
        )

    async def synchronize(self) -> BrokerBalance:
        """캐시를 무시하고 브로커를 내부 상태의 원천으로 다시 조회한다."""
        return await self.get_balance(force=True)

    @classmethod
    def _parse_position(cls, row: dict[str, Any]) -> BrokerPosition:
        return BrokerPosition(
            symbol=str(row.get("pdno") or ""),
            name=str(row.get("prdt_name") or ""),
            quantity=int(cls._decimal(row.get("hldg_qty"))),
            average_price=cls._decimal(row.get("pchs_avg_pric")),
            current_price=cls._decimal(row.get("prpr")),
            evaluation_amount=cls._decimal(row.get("evlu_amt")),
            evaluation_pnl=cls._decimal(row.get("evlu_pfls_amt")),
            return_rate=cls._decimal(row.get("evlu_pfls_rt")),
        )

    @staticmethod
    def _decimal(value: Any) -> Decimal:
        normalized = str(value or "0").replace(",", "").strip()
        try:
            return Decimal(normalized)
        except InvalidOperation:
            return Decimal("0")

