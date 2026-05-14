from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AgentModel
from .base import BaseRepository


class AgentRepository(BaseRepository[AgentModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AgentModel)

    async def get_by_name(self, name: str) -> AgentModel | None:
        query = select(AgentModel).where(AgentModel.name == name)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_active(self) -> list[AgentModel]:
        query = select(AgentModel).where(AgentModel.is_active.is_(True))
        result = await self.session.execute(query)
        return list(result.scalars().all())