from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseRepository
from ..models import MessageModel
from ..schemas import MessageCreate, MessageRole


class MessageRepository(BaseRepository[MessageModel]):
    """Repository for message operations."""

    @property
    def model_class(self):
        return MessageModel

    async def add_message(self, message_data: MessageCreate) -> MessageModel:
        """Append a message to conversation."""
        return await self.create(**message_data.model_dump())

    async def get_messages(
        self,
        session_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 50
    ) -> List[MessageModel]:
        """Get paginated messages, optionally filtered by session."""
        filters = {}
        if session_id:
            filters["session_id"] = session_id

        return await self.filter(
            filters=filters,
            order_by="timestamp",
            order_desc=False,
            skip=skip,
            limit=limit
        )

    async def get_recent_messages(
        self,
        session_id: str,
        limit: int = 10
    ) -> List[MessageModel]:
        """Get last N messages from a session."""
        result = await self.session.execute(
            select(MessageModel)
            .where(MessageModel.session_id == session_id)
            .order_by(desc(MessageModel.timestamp))
            .limit(limit)
        )
        # Reverse to get chronological order
        messages = list(result.scalars().all())
        messages.reverse()
        return messages

    async def search_messages(
        self,
        query: str,
        session_id: Optional[str] = None,
        role: Optional[MessageRole] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 50
    ) -> List[MessageModel]:
        """Search messages by content."""
        conditions = []

        # Text search in content
        if query:
            conditions.append(MessageModel.content.ilike(f"%{query}%"))

        # Optional filters
        if session_id:
            conditions.append(MessageModel.session_id == session_id)
        if role:
            conditions.append(MessageModel.role == role.value)
        if start_date:
            conditions.append(MessageModel.timestamp >= start_date)
        if end_date:
            conditions.append(MessageModel.timestamp <= end_date)

        search_query = select(MessageModel)
        if conditions:
            search_query = search_query.where(and_(*conditions))

        search_query = search_query.order_by(desc(MessageModel.timestamp)).offset(skip).limit(limit)

        result = await self.session.execute(search_query)
        return list(result.scalars().all())

    async def delete_messages(self, session_id: str) -> int:
        """Delete all messages from a session."""
        result = await self.session.execute(
            select(func.count(MessageModel.id))
            .where(MessageModel.session_id == session_id)
        )
        count = result.scalar()

        await self.session.execute(
            select(MessageModel).where(MessageModel.session_id == session_id)
        )

        return count or 0

    async def count_messages(
        self,
        session_id: Optional[str] = None,
        role: Optional[MessageRole] = None
    ) -> int:
        """Count messages with optional filters."""
        filters = {}
        if session_id:
            filters["session_id"] = session_id
        if role:
            filters["role"] = role.value

        return await self.count(filters)

    async def get_message_stats(self, session_id: str) -> Dict[str, Any]:
        """Get message statistics for a session."""
        result = await self.session.execute(
            select(
                func.count(MessageModel.id).label("total_messages"),
                func.sum(func.length(MessageModel.content)).label("total_characters"),
                func.avg(func.length(MessageModel.content)).label("avg_length"),
                func.min(MessageModel.timestamp).label("first_message"),
                func.max(MessageModel.timestamp).label("last_message"),
                func.count(func.distinct(MessageModel.role)).label("unique_roles")
            )
            .where(MessageModel.session_id == session_id)
        )

        row = result.first()
        if not row:
            return {
                "total_messages": 0,
                "total_characters": 0,
                "avg_length": 0.0,
                "first_message": None,
                "last_message": None,
                "unique_roles": 0,
            }

        return {
            "total_messages": row.total_messages or 0,
            "total_characters": row.total_characters or 0,
            "avg_length": float(row.avg_length) if row.avg_length else 0.0,
            "first_message": row.first_message,
            "last_message": row.last_message,
            "unique_roles": row.unique_roles or 0,
        }

    async def get_messages_by_role(
        self,
        session_id: str,
        role: MessageRole,
        skip: int = 0,
        limit: int = 50
    ) -> List[MessageModel]:
        """Get messages by role for a session."""
        return await self.filter(
            filters={"session_id": session_id, "role": role.value},
            order_by="timestamp",
            order_desc=False,
            skip=skip,
            limit=limit
        )

    async def get_conversation_summary(self, session_id: str) -> List[Dict[str, Any]]:
        """Get conversation summary with message counts by role."""
        result = await self.session.execute(
            select(
                MessageModel.role,
                func.count(MessageModel.id).label("count"),
                func.sum(func.length(MessageModel.content)).label("total_chars")
            )
            .where(MessageModel.session_id == session_id)
            .group_by(MessageModel.role)
        )

        summary = []
        for row in result:
            summary.append({
                "role": row.role,
                "count": row.count,
                "total_characters": row.total_chars or 0,
            })

        return summary

    async def bulk_add_messages(self, messages: List[MessageCreate]) -> List[MessageModel]:
        """Bulk add multiple messages."""
        message_dicts = [msg.model_dump() for msg in messages]
        return await self.bulk_create(message_dicts)

    async def get_messages_in_time_range(
        self,
        session_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[MessageModel]:
        """Get messages within a time range."""
        result = await self.session.execute(
            select(MessageModel)
            .where(
                and_(
                    MessageModel.session_id == session_id,
                    MessageModel.timestamp >= start_time,
                    MessageModel.timestamp <= end_time
                )
            )
            .order_by(MessageModel.timestamp)
        )
        return list(result.scalars().all())