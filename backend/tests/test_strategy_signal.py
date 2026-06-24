from datetime import UTC, datetime
from decimal import Decimal

from app.strategies.base import MarketSnapshot
from app.strategies.orb_vwap_volume import OrbVwapVolumeStrategy


def snapshot(**overrides) -> MarketSnapshot:
    values = {
        "symbol": "005930",
        "timestamp": datetime.now(UTC),
        "price": Decimal("71000"),
        "opening_range_high": Decimal("70000"),
        "vwap": Decimal("70500"),
        "current_volume": 2500,
        "average_volume": Decimal("1000"),
        "already_held": False,
        "has_pending_order": False,
    }
    values.update(overrides)
    return MarketSnapshot(**values)


def test_strategy_generates_signal_only_when_all_filters_pass() -> None:
    signal = OrbVwapVolumeStrategy().evaluate(snapshot())
    assert signal is not None
    assert signal.action == "BUY"


def test_strategy_blocks_when_pending_order_exists() -> None:
    assert OrbVwapVolumeStrategy().evaluate(snapshot(has_pending_order=True)) is None


def test_strategy_blocks_below_vwap() -> None:
    assert OrbVwapVolumeStrategy().evaluate(snapshot(price=Decimal("70400"))) is None

