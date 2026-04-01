from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AgentModel
from ..repositories import AgentRepository


class AgentService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = AgentRepository(session)

    async def get(self, agent_id: UUID) -> AgentModel | None:
        return await self.repository.get(agent_id)

    async def create(self, data: dict) -> AgentModel:
        return await self.repository.create(AgentModel(**data))

    async def update(self, agent_id: UUID, data: dict) -> AgentModel | None:
        return await self.repository.update(agent_id, data)

    async def delete(self, agent_id: UUID) -> bool:
        return await self.repository.delete(agent_id)
