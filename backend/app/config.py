from enum import StrEnum
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class TradingMode(StrEnum):
    SIM = "SIM"
    PAPER = "PAPER"
    LIVE = "LIVE"


class Settings(BaseSettings):
    """환경변수 기반 설정. 비밀값은 기본값을 두지 않는다."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "PulseTrade"
    environment: str = "development"
    trading_mode: TradingMode = TradingMode.SIM
    enable_live_trading: bool = False
    live_confirmation_phrase: str = "I_UNDERSTAND_LIVE_TRADING_RISK"

    kis_app_key: str = ""
    kis_app_secret: str = ""
    kis_account_number: str = ""
    kis_account_product_code: str = "01"
    kis_base_url: str = ""
    kis_websocket_url: str = ""
    kis_hts_id: str = ""

    database_url: str = "sqlite+aiosqlite:///./pulsetrade.db"
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    max_order_amount_krw: int = 100_000
    max_daily_loss_krw: int = 50_000
    max_daily_orders: int = 5
    max_position_amount_krw: int = 300_000
    strategy_symbols: str = "005930"
    scanner_symbols: str = (
        "005930,000660,373220,207940,005380,000270,035420,035720,068270,105560,"
        "055550,012330,028260,005490,066570,096770,051910,006400,003670,035250,"
        "323410,034020,086790,015760,032830,033780,017670,009150,011200,042660"
    )
    scanner_min_trade_value_krw: int = 30_000_000_000
    scanner_min_volume_spike: float = 1.3
    scanner_min_change_pct: float = 0.2
    scanner_max_change_pct: float = 12.0
    scanner_max_spread_bps: float = 20.0
    scanner_max_candidates: int = 8
    auto_order_budget_krw: int = 100_000
    strategy_stop_loss_pct: float = -1.0
    strategy_take_profit_pct: float = 2.0
    strategy_volume_multiplier: float = 2.0
    signal_buy_threshold: float = 70.0
    signal_sell_threshold: float = -60.0
    signal_exit_threshold: float = -80.0
    signal_weight_orb: float = 25.0
    signal_weight_volume: float = 20.0
    signal_weight_vwap: float = 15.0
    signal_weight_orderbook: float = 15.0
    signal_weight_trade_strength: float = 15.0
    signal_weight_momentum: float = 10.0
    signal_weight_trend: float = 10.0
    signal_weight_price_location: float = 12.0
    signal_weight_trend_structure: float = 12.0
    signal_weight_breakout: float = 14.0
    signal_weight_pullback: float = 8.0
    signal_weight_moving_average: float = 10.0
    signal_weight_candle: float = 6.0
    signal_weight_momentum_indicators: float = 8.0
    signal_weight_risk_reward: float = 10.0
    signal_weight_market_regime: float = 8.0
    market_proxy_symbols: str = "069500,229200"
    order_reconcile_interval_seconds: float = 3.0
    sim_initial_cash_krw: int = 10_000_000
    sim_commission_bps: float = 1.5
    sim_sell_tax_bps: float = 18.0
    sim_latency_ms: int = 150
    max_spread_bps: float = 20.0
    max_quote_age_seconds: float = 2.0
    volatility_guard_move_pct: float = 2.0
    volatility_guard_cooldown_seconds: int = 120
    strategy_order_ttl_seconds: float = 3.0
    strategy_max_reprices: int = 2
    strategy_max_holding_minutes: int = 30
    strategy_force_exit_time: str = "151500"

    @field_validator("trading_mode", mode="before")
    @classmethod
    def normalize_trading_mode(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().upper()
        return value

    @property
    def strategy_symbol_list(self) -> list[str]:
        return [
            symbol.strip()
            for symbol in self.strategy_symbols.split(",")
            if symbol.strip().isdigit() and len(symbol.strip()) == 6
        ]

    @property
    def scanner_symbol_list(self) -> list[str]:
        seen: set[str] = set()
        symbols: list[str] = []
        for symbol in self.scanner_symbols.split(","):
            normalized = symbol.strip()
            if normalized.isdigit() and len(normalized) == 6 and normalized not in seen:
                seen.add(normalized)
                symbols.append(normalized)
        return symbols

    @property
    def market_proxy_symbol_list(self) -> list[str]:
        return [
            symbol.strip()
            for symbol in self.market_proxy_symbols.split(",")
            if symbol.strip().isdigit() and len(symbol.strip()) == 6
        ]

    @property
    def kis_is_paper(self) -> bool:
        return "openapivts.koreainvestment.com" in self.kis_base_url.lower()

    @property
    def kis_is_live(self) -> bool:
        return "openapi.koreainvestment.com" in self.kis_base_url.lower() and not self.kis_is_paper

    @property
    def kis_configured(self) -> bool:
        return bool(
            self.kis_app_key
            and self.kis_app_secret
            and self.kis_base_url
            and self.kis_account_number
            and self.kis_account_product_code
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
