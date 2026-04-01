from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AgentToolModel
from .base import BaseRepository


class AgentToolRepository(BaseRepository[AgentToolModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AgentToolModel)

    async def list_by_agent(self, agent_id: UUID) -> list[AgentToolModel]:
        query = select(AgentToolModel).where(AgentToolModel.agent_id == agent_id)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def replace_for_agent(self, agent_id: UUID, tools: list[AgentToolModel]) -> list[AgentToolModel]:
        await self.session.execute(delete(AgentToolModel).where(AgentToolModel.agent_id == agent_id))
        created: list[AgentToolModel] = []
        for tool in tools:
            tool.agent_id = agent_id
            created.append(await self.create(tool))
        return created