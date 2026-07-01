from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from time import monotonic
from typing import Any

from app.kis.auth import KISAuthService
from app.kis.client import KISClient, KISConfigurationError
from app.strategies.base import OrderBookSnapshot

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
    change_pct: Decimal = Decimal("0")
    trade_value: Decimal = Decimal("0")


@dataclass(frozen=True)
class MinuteBar:
    symbol: str
    time: str
    price: Decimal
    high: Decimal
    low: Decimal
    volume: int
    open: Decimal = Decimal("0")


@dataclass(frozen=True)
class RankingRow:
    rank: int
    symbol: str
    name: str
    price: Decimal
    change_pct: Decimal
    volume: int
    trade_value: Decimal
    score: Decimal
    source: str


@dataclass(frozen=True)
class StockProfileData:
    symbol: str
    name: str
    market: str
    sector: str
    product: str
    listed_shares: int
    capital: Decimal
    par_value: Decimal


class KISMarketService:
    def __init__(self, client: KISClient, auth: KISAuthService) -> None:
        self.client = client
        self.auth = auth
        self._trading_day_cache: tuple[str, bool] | None = None
        self._vi_cache: dict[str, tuple[float, bool]] = {}
        self._quote_cache: dict[str, tuple[float, Quote]] = {}
        self._orderbook_cache: dict[str, tuple[float, OrderBookSnapshot]] = {}
        self._minute_cache: dict[str, tuple[float, list[MinuteBar]]] = {}
        self._period_cache: dict[str, tuple[float, list[MinuteBar]]] = {}
        self._ranking_cache: dict[str, tuple[float, list[RankingRow]]] = {}
        self._profile_cache: dict[str, tuple[float, StockProfileData]] = {}

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
            change_pct=self._decimal(output.get("prdy_ctrt")),
            trade_value=self._decimal(output.get("acml_tr_pbmn")),
        )
        self._quote_cache[symbol] = (monotonic(), quote)
        return quote

    async def get_orderbook(self, symbol: str) -> OrderBookSnapshot:
        cached = self._orderbook_cache.get(symbol)
        if cached and monotonic() - cached[0] < 2:
            return cached[1]
        await self.auth.ensure_access_token()
        body = await self.client.request(
            "GET",
            "/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn",
            tr_id="FHKST01010200",
            params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": symbol},
        )
        output = body.get("output1") or body.get("output") or {}
        if isinstance(output, list):
            output = output[0] if output else {}
        orderbook = OrderBookSnapshot(
            best_ask=self._decimal(output.get("askp1") or output.get("askp")),
            best_bid=self._decimal(output.get("bidp1") or output.get("bidp")),
            total_ask_quantity=self._int(output.get("total_askp_rsqn") or output.get("askp_rsqn")),
            total_bid_quantity=self._int(output.get("total_bidp_rsqn") or output.get("bidp_rsqn")),
            best_ask_quantity=self._int(output.get("askp_rsqn1")),
            best_bid_quantity=self._int(output.get("bidp_rsqn1")),
            received_at=datetime.now().astimezone(),
        )
        self._orderbook_cache[symbol] = (monotonic(), orderbook)
        return orderbook

    async def get_ranking(self, ranking_type: str, *, limit: int = 20) -> list[RankingRow]:
        config = self._ranking_config(ranking_type)
        cache_key = f"{ranking_type}:{limit}"
        cached = self._ranking_cache.get(cache_key)
        if cached and monotonic() - cached[0] < 20:
            return cached[1]
        await self.auth.ensure_access_token()
        body = await self.client.request(
            "GET",
            config["path"],
            tr_id=config["tr_id"],
            params=config["params"],
        )
        rows = body.get("output") or body.get("output1") or body.get("output2") or []
        if isinstance(rows, dict):
            rows = [rows]
        parsed = [
            self._parse_ranking_row(index + 1, row, ranking_type)
            for index, row in enumerate(rows[:limit])
            if isinstance(row, dict)
        ]
        self._ranking_cache[cache_key] = (monotonic(), parsed)
        return parsed

    async def get_stock_profile(self, symbol: str) -> StockProfileData:
        cached = self._profile_cache.get(symbol)
        if cached and monotonic() - cached[0] < 3600:
            return cached[1]
        await self.auth.ensure_access_token()
        body = await self.client.request(
            "GET",
            "/uapi/domestic-stock/v1/quotations/search-stock-info",
            tr_id="CTPF1002R",
            params={
                "PDNO": symbol,
                "PRDT_TYPE_CD": "300",
            },
        )
        output = body.get("output") or {}
        if isinstance(output, list):
            output = output[0] if output else {}
        profile = StockProfileData(
            symbol=symbol,
            name=str(
                output.get("prdt_name")
                or output.get("prdt_abrv_name")
                or output.get("hts_kor_isnm")
                or KNOWN_STOCK_NAMES.get(symbol, "")
            ),
            market=str(output.get("mket_id_cd") or output.get("rprs_mrkt_kor_name") or ""),
            sector=str(output.get("std_idst_clsf_cd_name") or output.get("idx_bztp_lcls_cd_name") or ""),
            product=str(output.get("prdt_eng_name") or output.get("scty_grp_id_name") or ""),
            listed_shares=self._int(output.get("lstg_stqt") or output.get("lstg_stcn")),
            capital=self._decimal(output.get("cpfn")),
            par_value=self._decimal(output.get("papr")),
        )
        self._profile_cache[symbol] = (monotonic(), profile)
        return profile

    async def get_market_indices(self) -> list[Quote]:
        rows: list[Quote] = []
        for symbol in ("0001", "1001"):
            try:
                rows.append(await self._get_index_quote(symbol))
            except Exception:
                continue
        return rows

    async def _get_index_quote(self, symbol: str) -> Quote:
        await self.auth.ensure_access_token()
        body = await self.client.request(
            "GET",
            "/uapi/domestic-stock/v1/quotations/inquire-index-price",
            tr_id="FHPUP02100000",
            params={
                "FID_COND_MRKT_DIV_CODE": "U",
                "FID_INPUT_ISCD": symbol,
            },
        )
        output = body.get("output") or {}
        if isinstance(output, list):
            output = output[0] if output else {}
        return Quote(
            symbol=symbol,
            name="KOSPI" if symbol == "0001" else "KOSDAQ",
            price=self._decimal(output.get("bstp_nmix_prpr") or output.get("stck_prpr")),
            volume=self._int(output.get("acml_vol")),
            change_pct=self._decimal(output.get("bstp_nmix_prdy_ctrt") or output.get("prdy_ctrt")),
            trade_value=self._decimal(output.get("acml_tr_pbmn")),
        )

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

    @staticmethod
    def _ranking_config(ranking_type: str) -> dict[str, Any]:
        common = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_COND_SCR_DIV_CODE": "20171",
            "FID_INPUT_ISCD": "0000",
            "FID_TRGT_CLS_CODE": "0",
            "FID_TRGT_EXLS_CLS_CODE": "0",
            "FID_INPUT_PRICE_1": "",
            "FID_INPUT_PRICE_2": "",
            "FID_VOL_CNT": "",
        }
        configs: dict[str, dict[str, Any]] = {
            "volume": {
                "tr_id": "FHPST01710000",
                "path": "/uapi/domestic-stock/v1/quotations/volume-rank",
                "params": {**common, "FID_RANK_SORT_CLS_CODE": "0", "FID_BLNG_CLS_CODE": "0"},
            },
            "change": {
                "tr_id": "FHPST01700000",
                "path": "/uapi/domestic-stock/v1/quotations/fluctuation",
                "params": {
                    **common,
                    "FID_RANK_SORT_CLS_CODE": "0",
                    "FID_INPUT_CNT_1": "0",
                    "FID_PRC_CLS_CODE": "0",
                    "FID_DIV_CLS_CODE": "0",
                    "FID_RSFL_RATE1": "",
                    "FID_RSFL_RATE2": "",
                },
            },
            "trade_strength": {
                "tr_id": "FHPST01680000",
                "path": "/uapi/domestic-stock/v1/quotations/trade-volume",
                "params": {**common, "FID_RANK_SORT_CLS_CODE": "0"},
            },
            "quote_balance": {
                "tr_id": "FHPST01720000",
                "path": "/uapi/domestic-stock/v1/quotations/quote-balance",
                "params": {**common, "FID_RANK_SORT_CLS_CODE": "0"},
            },
            "market_cap": {
                "tr_id": "FHPST01740000",
                "path": "/uapi/domestic-stock/v1/quotations/market-cap",
                "params": {**common, "FID_RANK_SORT_CLS_CODE": "0"},
            },
            "near_high_low": {
                "tr_id": "FHPST01800000",
                "path": "/uapi/domestic-stock/v1/quotations/near-new-highlow",
                "params": {**common, "FID_RANK_SORT_CLS_CODE": "0"},
            },
        }
        if ranking_type not in configs:
            raise KISConfigurationError("Unsupported ranking type")
        return configs[ranking_type]

    @classmethod
    def _parse_ranking_row(
        cls, fallback_rank: int, row: dict[str, Any], ranking_type: str
    ) -> RankingRow:
        symbol = str(
            row.get("mksc_shrn_iscd")
            or row.get("stck_shrn_iscd")
            or row.get("pdno")
            or row.get("iscd")
            or ""
        )
        rank = cls._int(row.get("data_rank") or row.get("rank") or fallback_rank)
        price = cls._decimal(row.get("stck_prpr") or row.get("prpr") or row.get("now_pric"))
        change_pct = cls._decimal(
            row.get("prdy_ctrt") or row.get("prdy_vrss_sign_rate") or row.get("rate")
        )
        volume = cls._int(row.get("acml_vol") or row.get("vol") or row.get("cntg_vol"))
        trade_value = cls._decimal(
            row.get("acml_tr_pbmn") or row.get("tr_pbmn") or row.get("avrg_vol")
        )
        score = cls._decimal(
            row.get("tday_rltv") or row.get("cntg_cls_code") or row.get("stck_sdpr")
        )
        return RankingRow(
            rank=rank if rank > 0 else fallback_rank,
            symbol=symbol,
            name=str(row.get("hts_kor_isnm") or row.get("prdt_name") or KNOWN_STOCK_NAMES.get(symbol, "")),
            price=price,
            change_pct=change_pct,
            volume=volume,
            trade_value=trade_value,
            score=score,
            source=ranking_type,
        )

    @staticmethod
    def _decimal(value: Any) -> Decimal:
        try:
            return Decimal(str(value or "0").replace(",", ""))
        except (InvalidOperation, ValueError):
            return Decimal("0")

    @staticmethod
    def _int(value: Any) -> int:
        try:
            return int(Decimal(str(value or "0").replace(",", "")))
        except (InvalidOperation, ValueError):
            return 0
