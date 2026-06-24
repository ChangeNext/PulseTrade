from enum import StrEnum
from functools import lru_cache

from pydantic import Field
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
