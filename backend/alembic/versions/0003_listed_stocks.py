"""listed stocks

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "listed_stocks" not in inspector.get_table_names():
        op.create_table(
            "listed_stocks",
            sa.Column("symbol", sa.String(6), nullable=False),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("market", sa.String(40), nullable=False),
            sa.Column("sector", sa.String(240), nullable=False, server_default=""),
            sa.Column("product", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("symbol"),
        )
    indexes = {index["name"] for index in inspector.get_indexes("listed_stocks")}
    if "ix_listed_stocks_name" not in indexes:
        op.create_index("ix_listed_stocks_name", "listed_stocks", ["name"])
    if "ix_listed_stocks_market" not in indexes:
        op.create_index("ix_listed_stocks_market", "listed_stocks", ["market"])


def downgrade() -> None:
    op.drop_index("ix_listed_stocks_market", table_name="listed_stocks")
    op.drop_index("ix_listed_stocks_name", table_name="listed_stocks")
    op.drop_table("listed_stocks")
