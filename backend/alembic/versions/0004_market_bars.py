"""market bars cache

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "market_bars" not in inspector.get_table_names():
        op.create_table(
            "market_bars",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("symbol", sa.String(12), nullable=False),
            sa.Column("period", sa.String(12), nullable=False),
            sa.Column("time", sa.String(16), nullable=False),
            sa.Column("open", sa.Numeric(18, 2), nullable=False),
            sa.Column("high", sa.Numeric(18, 2), nullable=False),
            sa.Column("low", sa.Numeric(18, 2), nullable=False),
            sa.Column("close", sa.Numeric(18, 2), nullable=False),
            sa.Column("volume", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("source", sa.String(20), nullable=False, server_default="KIS"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("symbol", "period", "time", name="uq_market_bars_symbol_period_time"),
        )
    indexes = {index["name"] for index in inspector.get_indexes("market_bars")}
    if "ix_market_bars_symbol" not in indexes:
        op.create_index("ix_market_bars_symbol", "market_bars", ["symbol"])
    if "ix_market_bars_period" not in indexes:
        op.create_index("ix_market_bars_period", "market_bars", ["period"])
    if "ix_market_bars_time" not in indexes:
        op.create_index("ix_market_bars_time", "market_bars", ["time"])
    if "ix_market_bars_lookup" not in indexes:
        op.create_index("ix_market_bars_lookup", "market_bars", ["symbol", "period", "time"])


def downgrade() -> None:
    op.drop_index("ix_market_bars_lookup", table_name="market_bars")
    op.drop_index("ix_market_bars_time", table_name="market_bars")
    op.drop_index("ix_market_bars_period", table_name="market_bars")
    op.drop_index("ix_market_bars_symbol", table_name="market_bars")
    op.drop_table("market_bars")
