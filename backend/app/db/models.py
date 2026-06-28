from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class OrderRecord(TimestampMixin, Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    client_order_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    broker_order_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    broker_order_date: Mapped[str | None] = mapped_column(String(8), nullable=True, index=True)
    broker_org_no: Mapped[str | None] = mapped_column(String(32), nullable=True)
    symbol: Mapped[str] = mapped_column(String(12), index=True)
    side: Mapped[str] = mapped_column(String(8))
    quantity: Mapped[int] = mapped_column(Integer)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    order_type: Mapped[str] = mapped_column(String(16), default="LIMIT")
    source: Mapped[str] = mapped_column(String(16), default="MANUAL")
    strategy_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mode: Mapped[str] = mapped_column(String(10))
    state: Mapped[str] = mapped_column(String(32), index=True)
    filled_quantity: Mapped[int] = mapped_column(Integer, default=0)
    average_fill_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    reference_cost_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    rejection_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    commission: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    tax: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    reprice_count: Mapped[int] = mapped_column(Integer, default=0)
    parent_order_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    auto_reprice_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    message: Mapped[str] = mapped_column(Text, default="")


class FillRecord(TimestampMixin, Base):
    __tablename__ = "fills"
    __table_args__ = (UniqueConstraint("fill_key", name="uq_fills_fill_key"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    fill_key: Mapped[str] = mapped_column(String(160), index=True)
    order_id: Mapped[str] = mapped_column(String(36), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 2))


class EventLog(TimestampMixin, Base):
    __tablename__ = "event_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(32), index=True)
    level: Mapped[str] = mapped_column(String(16), default="INFO")
    message: Mapped[str] = mapped_column(Text)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")


class RuntimeState(TimestampMixin, Base):
    __tablename__ = "runtime_state"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


class ListedStock(TimestampMixin, Base):
    __tablename__ = "listed_stocks"

    symbol: Mapped[str] = mapped_column(String(6), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    market: Mapped[str] = mapped_column(String(40), index=True)
    sector: Mapped[str] = mapped_column(String(240), default="")
    product: Mapped[str] = mapped_column(Text, default="")


class StrategyEntry(TimestampMixin, Base):
    __tablename__ = "strategy_entries"
    __table_args__ = (UniqueConstraint("trading_date", "symbol", name="uq_strategy_entry_day_symbol"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trading_date: Mapped[str] = mapped_column(String(10), index=True)
    symbol: Mapped[str] = mapped_column(String(12), index=True)
    entry_order_id: Mapped[str] = mapped_column(String(36))
    exit_order_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    closed: Mapped[bool] = mapped_column(Boolean, default=False)
