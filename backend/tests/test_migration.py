import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.config import get_settings


def test_legacy_sqlite_order_is_preserved(tmp_path: Path, monkeypatch) -> None:
    database = tmp_path / "legacy.db"
    connection = sqlite3.connect(database)
    connection.executescript(
        """
        CREATE TABLE orders (
            id VARCHAR(36) PRIMARY KEY, broker_order_id VARCHAR(100), symbol VARCHAR(12) NOT NULL,
            side VARCHAR(8) NOT NULL, quantity INTEGER NOT NULL, price NUMERIC(18,2) NOT NULL,
            mode VARCHAR(10) NOT NULL, state VARCHAR(32) NOT NULL, message TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE fills (
            id INTEGER PRIMARY KEY AUTOINCREMENT, order_id VARCHAR(36) NOT NULL,
            quantity INTEGER NOT NULL, price NUMERIC(18,2) NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE event_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, category VARCHAR(32) NOT NULL,
            level VARCHAR(16) NOT NULL, message TEXT NOT NULL, payload_json TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO orders VALUES (
            'legacy-id', NULL, '005930', 'BUY', 1, 70000,
            'SIM', 'ORDER_SENT', 'legacy', CURRENT_TIMESTAMP
        );
        """
    )
    connection.commit()
    connection.close()

    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{database}")
    get_settings.cache_clear()
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.upgrade(config, "head")

    connection = sqlite3.connect(database)
    row = connection.execute(
        "SELECT id, client_order_id, source, order_type FROM orders"
    ).fetchone()
    connection.close()
    assert row == ("legacy-id", "legacy-id", "MANUAL", "LIMIT")
    get_settings.cache_clear()
