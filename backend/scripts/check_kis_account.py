"""민감값이나 잔액을 출력하지 않는 KIS 읽기 전용 연결 점검."""

import asyncio

from app.config import get_settings
from app.kis.account import KISAccountService
from app.kis.auth import KISAuthService
from app.kis.client import KISClient


async def main() -> None:
    settings = get_settings()
    if not settings.kis_configured:
        raise SystemExit("KIS configuration is incomplete")

    client = KISClient(settings.kis_base_url, settings.kis_app_key, settings.kis_app_secret)
    service = KISAccountService(
        client,
        KISAuthService(client),
        settings.kis_account_number,
        settings.kis_account_product_code,
        paper="openapivts.koreainvestment.com" in settings.kis_base_url.lower(),
    )
    try:
        balance = await service.get_balance(force=True)
        print("KIS_ACCOUNT_READ_OK")
        print(f"POSITION_COUNT={len(balance.positions)}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())

