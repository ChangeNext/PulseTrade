import asyncio
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.kis.auth import KISAuthService
from app.kis.client import KISClient, KISConfigurationError
from app.trading.risk_manager import OrderIntent

ORDER_PATH = "/uapi/domestic-stock/v1/trading/order-cash"
DAILY_ORDER_PATH = "/uapi/domestic-stock/v1/trading/inquire-daily-ccld"
CANCEL_PATH = "/uapi/domestic-stock/v1/trading/order-rvsecncl"
ORDERABLE_CASH_PATH = "/uapi/domestic-stock/v1/trading/inquire-psbl-order"


@dataclass(frozen=True)
class BrokerOrderResult:
    broker_order_id: str
    broker_org_no: str
    accepted: bool
    message: str


@dataclass(frozen=True)
class BrokerOrderSnapshot:
    broker_order_id: str
    broker_org_no: str
    symbol: str
    side: str
    quantity: int
    price: Decimal
    filled_quantity: int
    average_fill_price: Decimal | None
    cancelable_quantity: int
    state: str
    order_time: str
    order_date: str


class KISOrderService:
    """국내주식 현금 지정가 주문과 주문 상태 동기화 경계."""

    def __init__(
        self,
        client: KISClient,
        auth: KISAuthService,
        account_number: str,
        product_code: str,
        *,
        paper: bool,
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
        self._request_lock = asyncio.Lock()

    async def place_order(self, intent: OrderIntent) -> BrokerOrderResult:
        await self.auth.ensure_access_token()
        tr_id = ("VTTC0012U" if intent.side.upper() == "BUY" else "VTTC0011U") if self.paper else (
            "TTTC0012U" if intent.side.upper() == "BUY" else "TTTC0011U"
        )
        async with self._request_lock:
            body = await self.client.request(
                "POST",
                ORDER_PATH,
                tr_id=tr_id,
                json={
                    "CANO": self.account_number,
                    "ACNT_PRDT_CD": self.product_code,
                    "PDNO": intent.symbol,
                    "ORD_DVSN": "00",
                    "ORD_QTY": str(intent.quantity),
                    "ORD_UNPR": self._price_string(intent.price),
                    "EXCG_ID_DVSN_CD": "KRX",
                    "SLL_TYPE": "01" if intent.side.upper() == "SELL" else "",
                    "CNDT_PRIC": "",
                },
            )
        output = body.get("output") or {}
        broker_order_id = str(output.get("ODNO") or output.get("odno") or "")
        if not broker_order_id:
            raise KISConfigurationError("KIS order response did not include an order number")
        return BrokerOrderResult(
            broker_order_id=broker_order_id,
            broker_org_no=str(
                output.get("KRX_FWDG_ORD_ORGNO") or output.get("krx_fwdg_ord_orgno") or ""
            ),
            accepted=True,
            message=str(body.get("msg1") or "KIS accepted the order"),
        )

    async def get_orderable_cash(self, intent: OrderIntent) -> Decimal:
        await self.auth.ensure_access_token()
        async with self._request_lock:
            body = await self.client.request(
                "GET",
                ORDERABLE_CASH_PATH,
                tr_id="VTTC8908R" if self.paper else "TTTC8908R",
                params={
                    "CANO": self.account_number,
                    "ACNT_PRDT_CD": self.product_code,
                    "PDNO": intent.symbol,
                    "ORD_UNPR": self._price_string(intent.price),
                    "ORD_DVSN": "00",
                    "CMA_EVLU_AMT_ICLD_YN": "Y",
                    "OVRS_ICLD_YN": "Y",
                },
            )
        output = body.get("output") or {}
        return self._decimal(output.get("ord_psbl_cash") or output.get("nrcvb_buy_amt"))

    async def list_daily_orders(self, *, broker_order_id: str = "") -> list[BrokerOrderSnapshot]:
        await self.auth.ensure_access_token()
        today = datetime.now().strftime("%Y%m%d")
        tr_id = "VTTC0081R" if self.paper else "TTTC0081R"
        fk100 = ""
        nk100 = ""
        tr_cont = ""
        snapshots: list[BrokerOrderSnapshot] = []
        for _ in range(10):
            async with self._request_lock:
                response = await self.client.request_response(
                    "GET",
                    DAILY_ORDER_PATH,
                    tr_id=tr_id,
                    tr_cont=tr_cont,
                    params={
                        "CANO": self.account_number,
                        "ACNT_PRDT_CD": self.product_code,
                        "INQR_STRT_DT": today,
                        "INQR_END_DT": today,
                        "SLL_BUY_DVSN_CD": "00",
                        "PDNO": "",
                        "CCLD_DVSN": "00",
                        "INQR_DVSN": "00",
                        "INQR_DVSN_3": "00",
                        "ORD_GNO_BRNO": "",
                        "ODNO": broker_order_id,
                        "INQR_DVSN_1": "",
                        "CTX_AREA_FK100": fk100,
                        "CTX_AREA_NK100": nk100,
                        "EXCG_ID_DVSN_CD": "KRX",
                    },
                )
            rows = response.data.get("output1") or []
            if isinstance(rows, dict):
                rows = [rows]
            snapshots.extend(self._parse_snapshot(row) for row in rows if row)
            if response.headers.get("tr_cont", "") not in {"M", "F"}:
                break
            fk100 = str(response.data.get("ctx_area_fk100") or "")
            nk100 = str(response.data.get("ctx_area_nk100") or "")
            tr_cont = "N"
            await asyncio.sleep(0.5 if self.paper else 0.05)
        if broker_order_id:
            return [row for row in snapshots if row.broker_order_id == broker_order_id]
        return snapshots

    async def get_order_status(self, broker_order_id: str) -> BrokerOrderSnapshot | None:
        rows = await self.list_daily_orders(broker_order_id=broker_order_id)
        return rows[0] if rows else None

    async def cancel_order(
        self,
        *,
        broker_order_id: str,
        broker_org_no: str,
        quantity: int,
    ) -> BrokerOrderResult:
        if not broker_order_id or not broker_org_no:
            raise KISConfigurationError("Broker order number and organization number are required")
        await self.auth.ensure_access_token()
        async with self._request_lock:
            body = await self.client.request(
                "POST",
                CANCEL_PATH,
                tr_id="VTTC0013U" if self.paper else "TTTC0013U",
                json={
                    "CANO": self.account_number,
                    "ACNT_PRDT_CD": self.product_code,
                    "KRX_FWDG_ORD_ORGNO": broker_org_no,
                    "ORGN_ODNO": broker_order_id,
                    "ORD_DVSN": "00",
                    "RVSE_CNCL_DVSN_CD": "02",
                    "ORD_QTY": str(max(quantity, 0)),
                    "ORD_UNPR": "0",
                    "QTY_ALL_ORD_YN": "Y",
                    "EXCG_ID_DVSN_CD": "KRX",
                    "CNDT_PRIC": "",
                },
            )
        output = body.get("output") or {}
        return BrokerOrderResult(
            broker_order_id=str(output.get("ODNO") or output.get("odno") or broker_order_id),
            broker_org_no=str(
                output.get("KRX_FWDG_ORD_ORGNO")
                or output.get("krx_fwdg_ord_orgno")
                or broker_org_no
            ),
            accepted=True,
            message=str(body.get("msg1") or "KIS accepted the cancellation"),
        )

    @classmethod
    def _parse_snapshot(cls, row: dict[str, Any]) -> BrokerOrderSnapshot:
        quantity = cls._int(row.get("ord_qty"))
        filled = cls._int(row.get("tot_ccld_qty") or row.get("ccld_qty"))
        cancelable = cls._int(row.get("psbl_qty") or row.get("rmn_qty") or max(quantity - filled, 0))
        if filled >= quantity and quantity > 0:
            state = "FILLED"
        elif cancelable == 0 and cls._is_canceled(row):
            state = "CANCELED"
        elif filled > 0:
            state = "PARTIALLY_FILLED"
        else:
            state = "ORDER_SENT"
        avg = cls._decimal(row.get("avg_prvs") or row.get("avg_ccld_unpr") or row.get("ccld_unpr"))
        return BrokerOrderSnapshot(
            broker_order_id=str(row.get("odno") or row.get("ODNO") or ""),
            broker_org_no=str(row.get("ord_gno_brno") or row.get("krx_fwdg_ord_orgno") or ""),
            symbol=str(row.get("pdno") or ""),
            side="SELL" if str(row.get("sll_buy_dvsn_cd") or "").strip() == "01" else "BUY",
            quantity=quantity,
            price=cls._decimal(row.get("ord_unpr")),
            filled_quantity=filled,
            average_fill_price=avg if avg > 0 else None,
            cancelable_quantity=cancelable,
            state=state,
            order_time=str(row.get("ord_tmd") or ""),
            order_date=str(row.get("ord_dt") or datetime.now().strftime("%Y%m%d")),
        )

    @staticmethod
    def _is_canceled(row: dict[str, Any]) -> bool:
        text = " ".join(str(row.get(key) or "") for key in ("ord_dvsn_name", "rjct_rson_name"))
        return "취소" in text

    @staticmethod
    def _int(value: Any) -> int:
        try:
            return int(Decimal(str(value or "0").replace(",", "")))
        except (InvalidOperation, ValueError):
            return 0

    @staticmethod
    def _decimal(value: Any) -> Decimal:
        try:
            return Decimal(str(value or "0").replace(",", ""))
        except InvalidOperation:
            return Decimal("0")

    @staticmethod
    def _price_string(value: Decimal) -> str:
        return format(value.quantize(Decimal("1")), "f")
