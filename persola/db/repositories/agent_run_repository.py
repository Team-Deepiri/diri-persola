from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AgentRunModel
from .base import BaseRepository


class AgentRunRepository(BaseRepository[AgentRunModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AgentRunModel)

    async def list_by_agent(self, agent_id: UUID, limit: int = 100) -> list[AgentRunModel]:
        query = (
            select(AgentRunModel)
            .where(AgentRunModel.agent_id == agent_id)
            .order_by(desc(AgentRunModel.created_at))
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def mark_completed(
        self,
        item_id: UUID,
        *,
        status: str,
        response_message: str | None,
        provider: str | None,
        model: str | None,
        tokens_used: int | None = None,
    ) -> AgentRunModel | None:
        return await self.update(
            item_id,
            {
                "status": status,
                "response_message": response_message,
                "provider": provider,
                "model": model,
                "tokens_used": tokens_used,
                "completed_at": datetime.utcnow(),
            },
        )