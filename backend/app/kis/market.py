from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from time import monotonic

from app.kis.auth import KISAuthService
from app.kis.client import KISClient

KNOWN_STOCK_NAMES = {
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    "035420": "NAVER",
    "035720": "카카오",
    "005380": "현대차",
    "000270": "기아",
    "373220": "LG에너지솔루션",
    "207940": "삼성바이오로직스",
    "006400": "삼성SDI",
    "051910": "LG화학",
}


@dataclass(frozen=True)
class Quote:
    symbol: str
    name: str
    price: Decimal
    volume: int


@dataclass(frozen=True)
class MinuteBar:
    symbol: str
    time: str
    price: Decimal
    high: Decimal
    low: Decimal
    volume: int
    open: Decimal = Decimal("0")


class KISMarketService:
    def __init__(self, client: KISClient, auth: KISAuthService) -> None:
        self.client = client
        self.auth = auth
        self._trading_day_cache: tuple[str, bool] | None = None
        self._vi_cache: dict[str, tuple[float, bool]] = {}
        self._quote_cache: dict[str, tuple[float, Quote]] = {}
        self._minute_cache: dict[str, tuple[float, list[MinuteBar]]] = {}
        self._period_cache: dict[str, tuple[float, list[MinuteBar]]] = {}

    async def is_trading_day(self) -> bool:
        today = datetime.now().strftime("%Y%m%d")
        if self._trading_day_cache and self._trading_day_cache[0] == today:
            return self._trading_day_cache[1]
        await self.auth.ensure_access_token()
        body = await self.client.request(
            "GET",
            "/uapi/domestic-stock/v1/quotations/chk-holiday",
            tr_id="CTCA0903R",
            params={"BASS_DT": today, "CTX_AREA_NK": "", "CTX_AREA_FK": ""},
        )
        rows = body.get("output") or []
        if isinstance(rows, dict):
            rows = [rows]
        row = next((item for item in rows if str(item.get("bass_dt") or "") == today), None)
        is_open = bool(row and str(row.get("opnd_yn") or "N") == "Y")
        self._trading_day_cache = (today, is_open)
        return is_open

    async def get_current_price(self, symbol: str) -> Quote:
        cached = self._quote_cache.get(symbol)
        if cached and monotonic() - cached[0] < 2:
            return cached[1]
        await self.auth.ensure_access_token()
        body = await self.client.request(
            "GET",
            "/uapi/domestic-stock/v1/quotations/inquire-price",
            tr_id="FHKST01010100",
            params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": symbol},
        )
        output = body.get("output") or {}
        quote = Quote(
            symbol=symbol,
            name=str(
                output.get("hts_kor_isnm")
                or output.get("prdt_name")
                or KNOWN_STOCK_NAMES.get(symbol, "")
            ),
            price=Decimal(str(output.get("stck_prpr") or "0")),
            volume=int(output.get("acml_vol") or 0),
        )
        self._quote_cache[symbol] = (monotonic(), quote)
        return quote

    async def is_vi_active(self, symbol: str) -> bool:
        cached = self._vi_cache.get(symbol)
        if cached and monotonic() - cached[0] < 5:
            return cached[1]
        await self.auth.ensure_access_token()
        today = datetime.now().strftime("%Y%m%d")
        body = await self.client.request(
            "GET",
            "/uapi/domestic-stock/v1/quotations/inquire-vi-status",
            tr_id="FHPST01390000",
            params={
                "FID_DIV_CLS_CODE": "0",
                "FID_COND_SCR_DIV_CODE": "20139",
                "FID_MRKT_CLS_CODE": "0",
                "FID_INPUT_ISCD": symbol,
                "FID_RANK_SORT_CLS_CODE": "0",
                "FID_INPUT_DATE_1": today,
                "FID_TRGT_CLS_CODE": "0",
                "FID_TRGT_EXLS_CLS_CODE": "",
            },
        )
        rows = body.get("output") or []
        if isinstance(rows, dict):
            rows = [rows]
        matching = [
            row
            for row in rows
            if str(row.get("mksc_shrn_iscd") or "") == symbol
            and str(row.get("bsop_date") or today) == today
            and str(row.get("cntg_vi_hour") or "")
        ]
        latest = max(matching, key=lambda row: str(row.get("cntg_vi_hour") or ""), default=None)
        active = bool(latest and not str(latest.get("vi_cncl_hour") or "").strip())
        self._vi_cache[symbol] = (monotonic(), active)
        return active

    async def get_minute_bars(self, symbol: str, *, max_pages: int = 14) -> list[MinuteBar]:
        cache_key = f"{symbol}:{max_pages}"
        cached = self._minute_cache.get(cache_key)
        if cached and monotonic() - cached[0] < 15:
            return cached[1]
        await self.auth.ensure_access_token()
        cursor = datetime.now()
        found: dict[str, MinuteBar] = {}
        for _ in range(max_pages):
            body = await self.client.request(
                "GET",
                "/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice",
                tr_id="FHKST03010200",
                params={
                    "FID_ETC_CLS_CODE": "",
                    "FID_COND_MRKT_DIV_CODE": "J",
                    "FID_INPUT_ISCD": symbol,
                    "FID_INPUT_HOUR_1": cursor.strftime("%H%M%S"),
                    "FID_PW_DATA_INCU_YN": "N",
                },
            )
            rows = body.get("output2") or []
            times: list[str] = []
            for row in rows:
                time = str(row.get("stck_cntg_hour") or "")
                if not time:
                    continue
                times.append(time)
                found[time] = MinuteBar(
                    symbol=symbol,
                    time=time,
                    price=Decimal(str(row.get("stck_prpr") or "0")),
                    high=Decimal(str(row.get("stck_hgpr") or "0")),
                    low=Decimal(str(row.get("stck_lwpr") or "0")),
                    volume=int(row.get("cntg_vol") or 0),
                    open=Decimal(str(row.get("stck_oprc") or row.get("stck_prpr") or "0")),
                )
            if not times or min(times) <= "090000":
                break
            earliest = datetime.strptime(min(times), "%H%M%S") - timedelta(seconds=1)
            cursor = cursor.replace(
                hour=earliest.hour, minute=earliest.minute, second=earliest.second
            )
        bars = [found[key] for key in sorted(found)]
        self._minute_cache[cache_key] = (monotonic(), bars)
        return bars

    async def get_period_bars(self, symbol: str, period: str) -> list[MinuteBar]:
        period_code = {"day": "D", "week": "W", "month": "M"}[period]
        cache_key = f"{symbol}:{period_code}"
        cached = self._period_cache.get(cache_key)
        if cached and monotonic() - cached[0] < 60:
            return cached[1]

        end = datetime.now()
        start_days = {"D": 180, "W": 365 * 3, "M": 365 * 6}[period_code]
        start = end - timedelta(days=start_days)
        await self.auth.ensure_access_token()
        body = await self.client.request(
            "GET",
            "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice",
            tr_id="FHKST03010100",
            params={
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": symbol,
                "FID_INPUT_DATE_1": start.strftime("%Y%m%d"),
                "FID_INPUT_DATE_2": end.strftime("%Y%m%d"),
                "FID_PERIOD_DIV_CODE": period_code,
                "FID_ORG_ADJ_PRC": "0",
            },
        )
        rows = body.get("output2") or []
        if isinstance(rows, dict):
            rows = [rows]
        bars = [
            MinuteBar(
                symbol=symbol,
                time=str(row.get("stck_bsop_date") or ""),
                price=Decimal(str(row.get("stck_clpr") or "0")),
                high=Decimal(str(row.get("stck_hgpr") or "0")),
                low=Decimal(str(row.get("stck_lwpr") or "0")),
                volume=int(row.get("acml_vol") or 0),
                open=Decimal(str(row.get("stck_oprc") or row.get("stck_clpr") or "0")),
            )
            for row in rows
            if row.get("stck_bsop_date")
        ]
        bars = sorted(bars, key=lambda item: item.time)
        self._period_cache[cache_key] = (monotonic(), bars)
        return bars
