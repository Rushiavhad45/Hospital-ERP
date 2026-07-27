"""Repository base class.

Repositories own **queries only**. They may ``flush`` to obtain primary keys
but never ``commit`` — transaction boundaries belong to the service layer.
"""
from __future__ import annotations

from typing import Generic, Sequence, Type, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import Base

M = TypeVar("M", bound=Base)


class BaseRepository(Generic[M]):
    model: Type[M]

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, id_: int) -> M | None:
        return await self.db.get(self.model, id_)

    async def add(self, obj: M) -> M:
        self.db.add(obj)
        await self.db.flush()
        return obj

    async def delete(self, obj: M) -> None:
        await self.db.delete(obj)
        await self.db.flush()

    async def list_all(self, *order_by) -> Sequence[M]:
        stmt = select(self.model)
        if order_by:
            stmt = stmt.order_by(*order_by)
        return (await self.db.execute(stmt)).scalars().all()

    async def count(self) -> int:
        return (await self.db.execute(
            select(func.count()).select_from(self.model))).scalar_one()
