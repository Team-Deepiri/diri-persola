from __future__ import annotations

from typing import Any, Generic, TypeVar
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

ModelT = TypeVar("ModelT")


class BaseRepository(Generic[ModelT]):
    def __init__(self, session: AsyncSession, model: type[ModelT]) -> None:
        self.session = session
        self.model = model

    async def get(self, item_id: UUID) -> ModelT | None:
        query = select(self.model).where(self.model.id == item_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list(self, offset: int = 0, limit: int = 50) -> list[ModelT]:
        query = select(self.model).offset(offset).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def create(self, obj: ModelT) -> ModelT:
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def update(self, item_id: UUID, data: dict[str, Any]) -> ModelT | None:
        item = await self.get(item_id)
        if item is None:
            return None

        for field, value in data.items():
            if hasattr(item, field):
                setattr(item, field, value)

        await self.session.flush()
        await self.session.refresh(item)
        return item

    async def delete(self, item_id: UUID) -> bool:
        item = await self.get(item_id)
        if item is None:
            return False

        await self.session.delete(item)
        await self.session.flush()
        return True

    async def count(self) -> int:
        query = select(func.count()).select_from(self.model)
        result = await self.session.execute(query)
        return int(result.scalar_one())