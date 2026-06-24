import json

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EventLog, OrderRecord


class TradingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_order(self, order: OrderRecord) -> OrderRecord:
        self.session.add(order)
        await self.session.commit()
        await self.session.refresh(order)
        return order

    async def add_event(self, category: str, message: str, payload: dict | None = None) -> None:
        self.session.add(
            EventLog(category=category, message=message, payload_json=json.dumps(payload or {}, ensure_ascii=False))
        )
        await self.session.commit()

    async def recent_orders(self, limit: int = 100) -> list[OrderRecord]:
        result = await self.session.scalars(
            select(OrderRecord).order_by(desc(OrderRecord.created_at)).limit(limit)
        )
        return list(result)

