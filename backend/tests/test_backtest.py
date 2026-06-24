from datetime import datetime, timedelta
from decimal import Decimal

from app.backtesting import BacktestBar, BacktestEngine
from app.config import Settings


def test_backtest_includes_costs_and_take_profit() -> None:
    start = datetime.fromisoformat("2026-06-24T09:00:00+09:00")
    bars: list[BacktestBar] = []
    for index in range(25):
        close = Decimal("10000") if index < 20 else Decimal("10200")
        if index == 22:
            close = Decimal("10500")
        bars.append(
            BacktestBar(
                timestamp=start + timedelta(minutes=index),
                symbol="005930",
                close=close,
                high=close,
                low=close,
                volume=500 if index >= 20 else 100,
                best_ask=close,
                best_bid=close - Decimal("10"),
                ask_quantity=100,
                bid_quantity=900,
                trade_strength=Decimal("150"),
            )
        )
    settings = Settings(auto_order_budget_krw=100_000, max_spread_bps=20)
    result = BacktestEngine(settings, slippage_bps=Decimal("1")).run(bars)
    assert len(result.trades) == 1
    assert result.trades[0].exit_reason == "TAKE_PROFIT"
    assert result.trades[0].costs > 0
