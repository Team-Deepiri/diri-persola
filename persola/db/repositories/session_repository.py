from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import SessionModel
from .base import BaseRepository


class SessionRepository(BaseRepository[SessionModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, SessionModel)

    async def get_by_session_id(self, session_id: str) -> SessionModel | None:
        query = select(SessionModel).where(SessionModel.session_id == session_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_or_create(self, agent_id: UUID, session_id: str) -> SessionModel:
        existing = await self.get_by_session_id(session_id)
        if existing is not None:
            return existing

        session = SessionModel(agent_id=agent_id, session_id=session_id)
        return await self.create(session)

    async def increment_message_count(self, item_id: UUID) -> None:
        item = await self.get(item_id)
        if item is None:
            return

        item.message_count += 1
        item.last_message_at = datetime.utcnow()
        await self.session.flush()

    async def list_by_agent(self, agent_id: UUID) -> list[SessionModel]:
        query = select(SessionModel).where(SessionModel.agent_id == agent_id)
        result = await self.session.execute(query)
        return list(result.scalars().all())