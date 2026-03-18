from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import select, update, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .base import BaseRepository
from ..models import SessionModel, MessageModel
from ..schemas import SessionCreate, SessionUpdate


class SessionRepository(BaseRepository[SessionModel]):
    """Repository for session operations."""

    @property
    def model_class(self):
        return SessionModel

    async def create_session(self, session_data: SessionCreate) -> SessionModel:
        """Create a new conversation session."""
        return await self.create(**session_data.model_dump())

    async def get_session(self, session_id: str) -> Optional[SessionModel]:
        """Retrieve session by ID."""
        return await self.get_by_id(session_id)

    async def update_session(self, session_id: str, update_data: SessionUpdate) -> Optional[SessionModel]:
        """Update session metadata."""
        return await self.update(session_id, **update_data.model_dump(exclude_unset=True))

    async def list_sessions(
        self,
        persona_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        user_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 50
    ) -> List[SessionModel]:
        """List sessions with filtering options."""
        filters = {}
        if persona_id:
            filters["persona_id"] = persona_id
        if agent_id:
            filters["agent_id"] = agent_id
        if user_id:
            filters["user_id"] = user_id

        # Add date range filtering
        conditions = []
        if filters:
            for key, value in filters.items():
                if hasattr(SessionModel, key):
                    conditions.append(getattr(SessionModel, key) == value)

        if start_date:
            conditions.append(SessionModel.started_at >= start_date)
        if end_date:
            conditions.append(SessionModel.started_at <= end_date)

        query = select(SessionModel)
        if conditions:
            query = query.where(and_(*conditions))

        query = query.order_by(SessionModel.started_at.desc()).offset(skip).limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def delete_session(self, session_id: str) -> bool:
        """Delete session."""
        return await self.delete(session_id)

    async def get_session_messages(
        self,
        session_id: str,
        limit: int = 100
    ) -> List[MessageModel]:
        """Get conversation history for a session."""
        result = await self.session.execute(
            select(MessageModel)
            .where(MessageModel.session_id == session_id)
            .order_by(MessageModel.timestamp)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_recent_sessions(
        self,
        user_id: Optional[str] = None,
        limit: int = 10
    ) -> List[SessionModel]:
        """Get recent sessions for a user."""
        query = select(SessionModel).order_by(SessionModel.started_at.desc()).limit(limit)

        if user_id:
            query = query.where(SessionModel.user_id == user_id)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def end_session(self, session_id: str) -> Optional[SessionModel]:
        """Mark session as ended."""
        return await self.update(session_id, ended_at=datetime.utcnow())

    async def get_active_sessions(
        self,
        user_id: Optional[str] = None,
        persona_id: Optional[str] = None
    ) -> List[SessionModel]:
        """Get sessions that haven't ended yet."""
        query = select(SessionModel).where(SessionModel.ended_at.is_(None))

        conditions = []
        if user_id:
            conditions.append(SessionModel.user_id == user_id)
        if persona_id:
            conditions.append(SessionModel.persona_id == persona_id)

        if conditions:
            query = query.where(and_(*conditions))

        query = query.order_by(SessionModel.started_at.desc())

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_session_with_messages(self, session_id: str) -> Optional[SessionModel]:
        """Get session with all messages loaded."""
        result = await self.session.execute(
            select(SessionModel)
            .options(selectinload(SessionModel.messages))
            .where(SessionModel.id == session_id)
        )
        return result.scalar_one_or_none()

    async def cleanup_old_sessions(self, days_old: int = 30) -> int:
        """Delete sessions older than specified days."""
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)

        result = await self.session.execute(
            select(func.count(SessionModel.id))
            .where(and_(
                SessionModel.ended_at.is_not(None),
                SessionModel.ended_at < cutoff_date
            ))
        )
        count = result.scalar()

        # Delete old sessions
        await self.session.execute(
            select(SessionModel)
            .where(and_(
                SessionModel.ended_at.is_not(None),
                SessionModel.ended_at < cutoff_date
            ))
        )

        return count or 0

    async def get_session_stats(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get statistics for a session."""
        # Count messages by role
        result = await self.session.execute(
            select(
                func.count(MessageModel.id).label("total_messages"),
                func.sum(func.length(MessageModel.content)).label("total_characters"),
                func.avg(func.length(MessageModel.content)).label("avg_message_length"),
                func.count(func.distinct(MessageModel.role)).label("unique_roles")
            )
            .where(MessageModel.session_id == session_id)
        )

        row = result.first()
        if not row:
            return None

        return {
            "total_messages": row.total_messages or 0,
            "total_characters": row.total_characters or 0,
            "avg_message_length": float(row.avg_message_length) if row.avg_message_length else 0.0,
            "unique_roles": row.unique_roles or 0,
        }

    async def get_sessions_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        user_id: Optional[str] = None
    ) -> List[SessionModel]:
        """Get sessions within a date range."""
        query = select(SessionModel).where(
            and_(
                SessionModel.started_at >= start_date,
                SessionModel.started_at <= end_date
            )
        )

        if user_id:
            query = query.where(SessionModel.user_id == user_id)

        query = query.order_by(SessionModel.started_at.desc())

        result = await self.session.execute(query)
        return list(result.scalars().all())