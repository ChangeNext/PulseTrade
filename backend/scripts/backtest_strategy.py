import argparse
import csv
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from app.backtesting import BacktestBar, BacktestEngine
from app.config import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the PulseTrade intraday scorer against CSV bars")
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--slippage-bps", type=Decimal, default=Decimal("5"))
    args = parser.parse_args()
    with args.csv_path.open(encoding="utf-8-sig", newline="") as handle:
        bars = [
            BacktestBar(
                timestamp=datetime.fromisoformat(row["timestamp"]),
                symbol=row["symbol"],
                close=Decimal(row["close"]),
                high=Decimal(row["high"]),
                low=Decimal(row["low"]),
                volume=int(row["volume"]),
                best_ask=Decimal(row["best_ask"]),
                best_bid=Decimal(row["best_bid"]),
                ask_quantity=int(row["ask_quantity"]),
                bid_quantity=int(row["bid_quantity"]),
                trade_strength=Decimal(row["trade_strength"]),
                halted=row.get("halted", "false").lower() == "true",
            )
            for row in csv.DictReader(handle)
        ]
    result = BacktestEngine(get_settings(), slippage_bps=args.slippage_bps).run(bars)
    print(json.dumps({
        "trades": len(result.trades),
        "net_pnl": str(result.net_pnl),
        "win_rate": str(result.win_rate),
        "max_drawdown": str(result.max_drawdown),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
