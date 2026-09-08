from __future__ import annotations

from typing import Any, Generic, TypeVar
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.selectable import Select

ModelT = TypeVar("ModelT")
FilterT = TypeVar("FilterT", bound=tuple[Any, ...])


class BaseRepository(Generic[ModelT]):
    """CRUD base with optional tenant scoping.

    Passing a `tenant_id` scopes every CRUD operation to that tenant (the
    model must expose a `tenant_id` column, e.g. via ``TenantMixin``).
    Subclasses perform targeting queries (``get_by_name``, ``list_by_agent``,
    ...) through the ``_tenant_filter()`` helper so they stay scoped too.
    """

    def __init__(
        self,
        session: AsyncSession,
        model: type[ModelT],
        tenant_id: UUID | None = None,
    ) -> None:
        self.session = session
        self.model = model
        self.tenant_id = tenant_id

    @property
    def _is_tenant_scoped(self) -> bool:
        return self.tenant_id is not None and hasattr(self.model, "tenant_id")

    async def get(self, item_id: UUID) -> ModelT | None:
        query = select(self.model).where(self.model.id == item_id)
        query = self._tenant_filter(query)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list(self, offset: int = 0, limit: int = 50) -> list[ModelT]:
        query = self._tenant_filter(select(self.model)).offset(offset).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def create(self, obj: ModelT) -> ModelT:
        if self._is_tenant_scoped:
            setattr(obj, "tenant_id", self.tenant_id)
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
        query = self._tenant_filter(select(func.count()).select_from(self.model))
        result = await self.session.execute(query)
        return int(result.scalar_one())

    def _tenant_filter(self, query: Select[FilterT]) -> Select[FilterT]:
        """Apply the tenant predicate to a select, when tenant scoping is active."""
        if self._is_tenant_scoped:
            return query.where(self.model.tenant_id == self.tenant_id)
        return query