from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import Base
from app.db.repository import TradingRepository


@pytest.mark.asyncio
async def test_market_bars_are_upserted_and_returned_in_time_order() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        repository = TradingRepository(session)
        changed = await repository.upsert_market_bars(
            "005930",
            "day",
            [
                {
                    "time": "20260702",
                    "open": Decimal("70000"),
                    "high": Decimal("71000"),
                    "low": Decimal("69000"),
                    "close": Decimal("70500"),
                    "volume": 1000,
                },
                {
                    "time": "20260701",
                    "open": Decimal("68000"),
                    "high": Decimal("70200"),
                    "low": Decimal("67900"),
                    "close": Decimal("70000"),
                    "volume": 900,
                },
            ],
        )

        rows = await repository.market_bars("005930", "day")

    assert changed == 2
    assert [row.time for row in rows] == ["20260701", "20260702"]
    assert rows[-1].close == Decimal("70500")
    await engine.dispose()


@pytest.mark.asyncio
async def test_market_bar_upsert_updates_existing_row() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        repository = TradingRepository(session)
        await repository.upsert_market_bars(
            "005930",
            "1m",
            [{"time": "090000", "open": 100, "high": 101, "low": 99, "close": 100, "volume": 10}],
        )
        await repository.upsert_market_bars(
            "005930",
            "1m",
            [{"time": "090000", "open": 100, "high": 104, "low": 98, "close": 103, "volume": 25}],
            source="WS",
        )
        rows = await repository.market_bars("005930", "1m")

    assert len(rows) == 1
    assert rows[0].high == Decimal("104")
    assert rows[0].close == Decimal("103")
    assert rows[0].volume == 25
    assert rows[0].source == "WS"
    await engine.dispose()
