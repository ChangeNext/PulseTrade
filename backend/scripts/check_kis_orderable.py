"""민감값이나 잔액을 출력하지 않는 KIS 주문 전 읽기 전용 점검."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.kis.auth import KISAuthService
from app.kis.client import KISAPIError, KISClient
from app.kis.market import KISMarketService
from app.kis.order import KISOrderService
from app.trading.risk_manager import OrderIntent


async def main() -> None:
    settings = get_settings()
    if not settings.kis_configured:
        raise SystemExit("KIS configuration is incomplete")
    if not settings.kis_is_paper:
        raise SystemExit("KIS orderable check is restricted to PAPER base URL")

    symbol = (settings.strategy_symbol_list or ["005930"])[0]
    client = KISClient(settings.kis_base_url, settings.kis_app_key, settings.kis_app_secret)
    auth = KISAuthService(client)
    market = KISMarketService(client, auth)
    orders = KISOrderService(
        client,
        auth,
        settings.kis_account_number,
        settings.kis_account_product_code,
        paper=True,
    )
    try:
        quote = await market.get_current_price(symbol)
        cash = await orders.get_orderable_cash(
            OrderIntent(symbol=symbol, side="BUY", quantity=1, price=quote.price)
        )
        print("KIS_ORDERABLE_READ_OK")
        print(f"SYMBOL={symbol}")
        print(f"PRICE={quote.price}")
        print(f"ORDERABLE_CASH_READ={cash >= 0}")
    except KISAPIError as exc:
        print("KIS_ORDERABLE_READ_FAILED")
        print(f"STATUS_CODE={exc.status_code}")
        print(f"ERROR_CODE={exc.code}")
        print(f"MESSAGE={exc}")
        raise SystemExit(1) from exc
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
