"""persistent trading state

Revision ID: 0001
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "orders" not in tables:
        from app.db.models import Base

        Base.metadata.create_all(op.get_bind())
        return

    with op.batch_alter_table("orders") as batch:
        batch.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("client_order_id", sa.String(64), nullable=True))
        batch.add_column(sa.Column("broker_org_no", sa.String(32), nullable=True))
        batch.add_column(sa.Column("broker_order_date", sa.String(8), nullable=True))
        batch.add_column(sa.Column("order_type", sa.String(16), nullable=False, server_default="LIMIT"))
        batch.add_column(sa.Column("source", sa.String(16), nullable=False, server_default="MANUAL"))
        batch.add_column(sa.Column("strategy_name", sa.String(64), nullable=True))
        batch.add_column(sa.Column("filled_quantity", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("average_fill_price", sa.Numeric(18, 2), nullable=True))
        batch.add_column(sa.Column("reference_cost_price", sa.Numeric(18, 2), nullable=True))
        batch.add_column(sa.Column("rejection_code", sa.String(64), nullable=True))
    op.execute("UPDATE orders SET client_order_id = id, updated_at = created_at")
    with op.batch_alter_table("orders") as batch:
        batch.alter_column("client_order_id", nullable=False)
        batch.create_unique_constraint("uq_orders_client_order_id", ["client_order_id"])
        batch.create_index("ix_orders_client_order_id", ["client_order_id"])
        batch.create_index("ix_orders_broker_order_date", ["broker_order_date"])

    with op.batch_alter_table("fills") as batch:
        batch.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("fill_key", sa.String(160), nullable=True))
    op.execute("UPDATE fills SET fill_key = 'legacy-' || id, updated_at = created_at")
    with op.batch_alter_table("fills") as batch:
        batch.alter_column("fill_key", nullable=False)
        batch.create_unique_constraint("uq_fills_fill_key", ["fill_key"])
        batch.create_index("ix_fills_fill_key", ["fill_key"])

    with op.batch_alter_table("event_logs") as batch:
        batch.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE event_logs SET updated_at = created_at")

    op.create_table(
        "runtime_state",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "strategy_entries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("trading_date", sa.String(10), nullable=False),
        sa.Column("symbol", sa.String(12), nullable=False),
        sa.Column("entry_order_id", sa.String(36), nullable=False),
        sa.Column("exit_order_id", sa.String(36), nullable=True),
        sa.Column("closed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("trading_date", "symbol", name="uq_strategy_entry_day_symbol"),
    )
    op.create_index("ix_strategy_entries_trading_date", "strategy_entries", ["trading_date"])
    op.create_index("ix_strategy_entries_symbol", "strategy_entries", ["symbol"])


def downgrade() -> None:
    op.drop_table("strategy_entries")
    op.drop_table("runtime_state")
    with op.batch_alter_table("event_logs") as batch:
        batch.drop_column("updated_at")
    with op.batch_alter_table("fills") as batch:
        batch.drop_index("ix_fills_fill_key")
        batch.drop_constraint("uq_fills_fill_key", type_="unique")
        batch.drop_column("fill_key")
        batch.drop_column("updated_at")
    with op.batch_alter_table("orders") as batch:
        batch.drop_index("ix_orders_client_order_id")
        batch.drop_index("ix_orders_broker_order_date")
        batch.drop_constraint("uq_orders_client_order_id", type_="unique")
        for column in (
            "rejection_code", "reference_cost_price", "average_fill_price", "filled_quantity", "strategy_name", "source",
            "order_type", "broker_order_date", "broker_org_no", "client_order_id", "updated_at",
        ):
            batch.drop_column(column)
