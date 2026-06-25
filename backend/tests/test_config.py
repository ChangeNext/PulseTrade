from app.config import Settings, TradingMode


def test_trading_mode_is_case_insensitive() -> None:
    assert Settings(trading_mode="Live").trading_mode == TradingMode.LIVE
    assert Settings(trading_mode=" paper ").trading_mode == TradingMode.PAPER
