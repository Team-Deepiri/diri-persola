from __future__ import annotations

from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import MessageModel
from .base import BaseRepository


class MessageRepository(BaseRepository[MessageModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, MessageModel)

    async def add(self, session_id: UUID, role: str, content: str, **meta) -> MessageModel:
        message = MessageModel(
            session_id=session_id,
            role=role,
            content=content,
            message_metadata=meta,
        )
        return await self.create(message)

    async def get_history(self, session_id: UUID, limit: int = 50) -> list[MessageModel]:
        query = (
            select(MessageModel)
            .where(MessageModel.session_id == session_id)
            .order_by(MessageModel.created_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_recent(self, session_id: UUID, n: int) -> list[MessageModel]:
        query = (
            select(MessageModel)
            .where(MessageModel.session_id == session_id)
            .order_by(desc(MessageModel.created_at))
            .limit(n)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())