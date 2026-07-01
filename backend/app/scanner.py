import asyncio
from dataclasses import dataclass
from decimal import Decimal

from app.config import Settings
from app.kis.client import KISAPIError, KISConfigurationError
from app.kis.market import KISMarketService, MinuteBar, Quote
from app.strategies.base import OrderBookSnapshot


@dataclass(frozen=True)
class ScannerCandidate:
    symbol: str
    name: str
    price: Decimal
    change_pct: Decimal
    volume: int
    trade_value: Decimal
    vwap: Decimal
    volume_spike: Decimal
    spread_bps: Decimal
    score: Decimal
    passed: bool
    reasons: tuple[str, ...]


class StockScanner:
    def __init__(self, settings: Settings, market: KISMarketService) -> None:
        self.settings = settings
        self.market = market

    async def scan(self) -> list[ScannerCandidate]:
        symbols = await self._candidate_symbols()
        if not symbols:
            return []
        results = await asyncio.gather(
            *(self._scan_symbol(symbol) for symbol in symbols),
            return_exceptions=True,
        )
        candidates = [
            result for result in results if isinstance(result, ScannerCandidate)
        ]
        return sorted(candidates, key=lambda item: (item.passed, item.score), reverse=True)[
            : self.settings.scanner_max_candidates
        ]

    async def _candidate_symbols(self) -> list[str]:
        seen: set[str] = set()
        symbols: list[str] = []
        for ranking_type in ("volume", "change"):
            try:
                rows = await self.market.get_ranking(ranking_type, limit=20)
            except (AttributeError, KISAPIError, KISConfigurationError):
                continue
            for row in rows:
                if row.symbol and row.symbol not in seen:
                    seen.add(row.symbol)
                    symbols.append(row.symbol)
        for symbol in self.settings.scanner_symbol_list:
            if symbol not in seen:
                seen.add(symbol)
                symbols.append(symbol)
        return symbols[: max(self.settings.scanner_max_candidates * 4, 20)]

    async def _scan_symbol(self, symbol: str) -> ScannerCandidate:
        quote, bars, orderbook, vi_active = await asyncio.gather(
            self.market.get_current_price(symbol),
            self.market.get_minute_bars(symbol, max_pages=4),
            self.market.get_orderbook(symbol),
            self._vi_active(symbol),
        )
        vwap = self._vwap(bars)
        volume_spike = self._volume_spike(bars)
        spread_bps = self._spread_bps(orderbook)
        reasons = self._reasons(quote, vwap, volume_spike, spread_bps, vi_active)
        score = self._score(quote, volume_spike, spread_bps, vwap)
        if reasons:
            score -= Decimal(len(reasons) * 8)
        return ScannerCandidate(
            symbol=symbol,
            name=quote.name,
            price=quote.price,
            change_pct=quote.change_pct,
            volume=quote.volume,
            trade_value=quote.trade_value,
            vwap=vwap,
            volume_spike=volume_spike,
            spread_bps=spread_bps,
            score=max(score, Decimal("0")),
            passed=not reasons,
            reasons=tuple(reasons),
        )

    async def _vi_active(self, symbol: str) -> bool:
        try:
            return await self.market.is_vi_active(symbol)
        except (KISAPIError, KISConfigurationError):
            return True

    def _reasons(
        self,
        quote: Quote,
        vwap: Decimal,
        volume_spike: Decimal,
        spread_bps: Decimal,
        vi_active: bool,
    ) -> list[str]:
        reasons: list[str] = []
        if quote.price <= 0:
            reasons.append("PRICE_UNAVAILABLE")
        if quote.trade_value < Decimal(self.settings.scanner_min_trade_value_krw):
            reasons.append("LOW_TRADE_VALUE")
        if volume_spike < Decimal(str(self.settings.scanner_min_volume_spike)):
            reasons.append("LOW_VOLUME_SPIKE")
        if quote.change_pct < Decimal(str(self.settings.scanner_min_change_pct)):
            reasons.append("WEAK_CHANGE_RATE")
        if quote.change_pct > Decimal(str(self.settings.scanner_max_change_pct)):
            reasons.append("OVERHEATED_CHANGE_RATE")
        if vwap <= 0 or quote.price <= vwap:
            reasons.append("BELOW_VWAP")
        if spread_bps <= 0 or spread_bps > Decimal(str(self.settings.scanner_max_spread_bps)):
            reasons.append("WIDE_SPREAD")
        if vi_active:
            reasons.append("VI_OR_HALT_RISK")
        return reasons

    @staticmethod
    def _vwap(bars: list[MinuteBar]) -> Decimal:
        total_volume = sum(bar.volume for bar in bars)
        if total_volume <= 0:
            return Decimal("0")
        total_value = sum(bar.price * bar.volume for bar in bars)
        return total_value / Decimal(total_volume)

    @staticmethod
    def _volume_spike(bars: list[MinuteBar]) -> Decimal:
        if len(bars) < 6:
            return Decimal("0")
        current = bars[-1].volume
        previous = bars[-21:-1] if len(bars) >= 21 else bars[:-1]
        average = Decimal(sum(bar.volume for bar in previous)) / Decimal(len(previous))
        if average <= 0:
            return Decimal("0")
        return Decimal(current) / average

    @staticmethod
    def _spread_bps(orderbook: OrderBookSnapshot) -> Decimal:
        if orderbook.best_ask <= 0 or orderbook.best_bid <= 0:
            return Decimal("0")
        midpoint = (orderbook.best_ask + orderbook.best_bid) / Decimal("2")
        if midpoint <= 0:
            return Decimal("0")
        return (orderbook.best_ask - orderbook.best_bid) / midpoint * Decimal("10000")

    @staticmethod
    def _score(
        quote: Quote,
        volume_spike: Decimal,
        spread_bps: Decimal,
        vwap: Decimal,
    ) -> Decimal:
        liquidity = min(quote.trade_value / Decimal("100000000000"), Decimal("1")) * Decimal("25")
        volume = min(volume_spike / Decimal("3"), Decimal("1")) * Decimal("25")
        momentum = min(max(quote.change_pct, Decimal("0")) / Decimal("6"), Decimal("1")) * Decimal("20")
        spread = max(Decimal("0"), Decimal("1") - spread_bps / Decimal("20")) * Decimal("15")
        vwap_score = Decimal("0")
        if vwap > 0 and quote.price > vwap:
            vwap_score = min((quote.price - vwap) / vwap * Decimal("100"), Decimal("3")) / Decimal("3") * Decimal("15")
        return liquidity + volume + momentum + spread + vwap_score
