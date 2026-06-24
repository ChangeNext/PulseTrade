"""scalping execution fields

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("orders")}
    additions = [
        sa.Column("commission", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("tax", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("reprice_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("parent_order_id", sa.String(36), nullable=True),
        sa.Column("auto_reprice_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
    ]
    missing = [column for column in additions if column.name not in columns]
    if missing:
        with op.batch_alter_table("orders") as batch:
            for column in missing:
                batch.add_column(column)
    indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("orders")}
    if "ix_orders_parent_order_id" not in indexes:
        op.create_index("ix_orders_parent_order_id", "orders", ["parent_order_id"])


def downgrade() -> None:
    with op.batch_alter_table("orders") as batch:
        batch.drop_index("ix_orders_parent_order_id")
        batch.drop_column("auto_reprice_requested")
        batch.drop_column("parent_order_id")
        batch.drop_column("reprice_count")
        batch.drop_column("tax")
        batch.drop_column("commission")
