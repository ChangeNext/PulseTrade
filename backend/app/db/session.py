from collections.abc import AsyncIterator
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

settings = get_settings()
engine = create_async_engine(settings.database_url, future=True)
AsyncSessionFactory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionFactory() as session:
        yield session


async def init_db() -> None:
    backend_dir = Path(__file__).resolve().parents[2]
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "alembic"))
    config.set_main_option("sqlalchemy.url", settings.database_url.replace("+aiosqlite", ""))
    command.upgrade(config, "head")
