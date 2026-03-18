from typing import Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories.persona_repository import PersonaRepository
from ..repositories.agent_repository import AgentRepository
from ..repositories.session_repository import SessionRepository
from ..repositories.message_repository import MessageRepository
from ..models import PersonaModel, AgentModel, SessionModel, MessageModel


class AnalyticsService:
    """Business logic for analytics and statistics."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.persona_repo = PersonaRepository(session)
        self.agent_repo = AgentRepository(session)
        self.session_repo = SessionRepository(session)
        self.message_repo = MessageRepository(session)

    async def get_usage_stats(self) -> Dict[str, Any]:
        """Get overall usage statistics."""
        # Get counts
        persona_count = await self.persona_repo.count()
        agent_count = await self.agent_repo.count()
        session_count = await self.session_repo.count()
        message_count = await self.message_repo.count()

        # Get active sessions
        active_sessions = await self.session_repo.get_active_sessions()
        active_count = len(active_sessions)

        # Get date ranges
        result = await self.session.execute(
            select(
                func.min(SessionModel.started_at).label("first_session"),
                func.max(SessionModel.started_at).label("last_session"),
                func.min(MessageModel.timestamp).label("first_message"),
                func.max(MessageModel.timestamp).label("last_message"),
            )
        )
        row = result.first()

        return {
            "total_personas": persona_count,
            "total_agents": agent_count,
            "total_sessions": session_count,
            "total_messages": message_count,
            "active_sessions": active_count,
            "first_session": row.first_session if row else None,
            "last_session": row.last_session if row else None,
            "first_message": row.first_message if row else None,
            "last_message": row.last_message if row else None,
        }

    async def get_persona_usage(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get personas ranked by usage."""
        result = await self.session.execute(
            select(
                PersonaModel.id,
                PersonaModel.name,
                func.count(SessionModel.id).label("session_count"),
                func.count(MessageModel.id).label("message_count"),
                func.max(SessionModel.started_at).label("last_used"),
            )
            .outerjoin(SessionModel, PersonaModel.id == SessionModel.persona_id)
            .outerjoin(MessageModel, SessionModel.id == MessageModel.session_id)
            .group_by(PersonaModel.id, PersonaModel.name)
            .order_by(desc(func.count(SessionModel.id)))
            .limit(limit)
        )

        usage_stats = []
        for row in result:
            usage_stats.append({
                "persona_id": row.id,
                "persona_name": row.name,
                "session_count": row.session_count or 0,
                "message_count": row.message_count or 0,
                "last_used": row.last_used,
            })

        return usage_stats

    async def get_conversation_metrics(self) -> Dict[str, Any]:
        """Get conversation metrics."""
        # Message statistics
        result = await self.session.execute(
            select(
                func.count(MessageModel.id).label("total_messages"),
                func.avg(func.length(MessageModel.content)).label("avg_message_length"),
                func.sum(func.length(MessageModel.content)).label("total_characters"),
                func.count(func.distinct(MessageModel.session_id)).label("unique_sessions"),
            )
        )
        msg_stats = result.first()

        # Messages by role
        role_result = await self.session.execute(
            select(
                MessageModel.role,
                func.count(MessageModel.id).label("count"),
                func.avg(func.length(MessageModel.content)).label("avg_length"),
            )
            .group_by(MessageModel.role)
        )

        messages_by_role = {}
        for row in role_result:
            messages_by_role[row.role] = {
                "count": row.count,
                "avg_length": float(row.avg_length) if row.avg_length else 0.0,
            }

        # Session duration stats
        duration_result = await self.session.execute(
            select(
                func.avg(
                    func.extract('epoch', SessionModel.ended_at - SessionModel.started_at)
                ).label("avg_duration_seconds"),
                func.count(SessionModel.id).filter(SessionModel.ended_at.is_not(None)).label("completed_sessions"),
            )
        )
        duration_stats = duration_result.first()

        return {
            "total_messages": msg_stats.total_messages or 0,
            "avg_message_length": float(msg_stats.avg_message_length) if msg_stats.avg_message_length else 0.0,
            "total_characters": msg_stats.total_characters or 0,
            "unique_sessions": msg_stats.unique_sessions or 0,
            "messages_by_role": messages_by_role,
            "avg_session_duration_seconds": float(duration_stats.avg_duration_seconds) if duration_stats.avg_duration_seconds else 0.0,
            "completed_sessions": duration_stats.completed_sessions or 0,
        }

    async def cleanup_old_sessions(self, days_old: int = 30) -> Dict[str, Any]:
        """Clean up old sessions and return statistics."""
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)

        # Count sessions to be deleted
        result = await self.session.execute(
            select(func.count(SessionModel.id))
            .where(and_(
                SessionModel.ended_at.is_not(None),
                SessionModel.ended_at < cutoff_date
            ))
        )
        session_count = result.scalar()

        # Count messages to be deleted
        result = await self.session.execute(
            select(func.count(MessageModel.id))
            .join(SessionModel)
            .where(and_(
                SessionModel.ended_at.is_not(None),
                SessionModel.ended_at < cutoff_date
            ))
        )
        message_count = result.scalar()

        # Perform cleanup
        deleted_sessions = await self.session_repo.cleanup_old_sessions(days_old)

        return {
            "sessions_deleted": deleted_sessions,
            "messages_deleted": message_count or 0,
            "cutoff_date": cutoff_date,
        }

    async def get_daily_usage(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get daily usage statistics."""
        start_date = datetime.utcnow() - timedelta(days=days)

        result = await self.session.execute(
            select(
                func.date(SessionModel.started_at).label("date"),
                func.count(SessionModel.id).label("sessions"),
                func.count(MessageModel.id).label("messages"),
            )
            .outerjoin(MessageModel, SessionModel.id == MessageModel.session_id)
            .where(SessionModel.started_at >= start_date)
            .group_by(func.date(SessionModel.started_at))
            .order_by(func.date(SessionModel.started_at))
        )

        daily_stats = []
        for row in result:
            daily_stats.append({
                "date": row.date.isoformat(),
                "sessions": row.sessions or 0,
                "messages": row.messages or 0,
            })

        return daily_stats

    async def get_agent_performance(self) -> List[Dict[str, Any]]:
        """Get agent performance metrics."""
        result = await self.session.execute(
            select(
                AgentModel.id,
                AgentModel.name,
                func.count(SessionModel.id).label("total_sessions"),
                func.avg(
                    func.extract('epoch', SessionModel.ended_at - SessionModel.started_at)
                ).label("avg_session_duration"),
                func.count(MessageModel.id).label("total_messages"),
                func.max(SessionModel.started_at).label("last_active"),
            )
            .outerjoin(SessionModel, AgentModel.id == SessionModel.agent_id)
            .outerjoin(MessageModel, SessionModel.id == MessageModel.session_id)
            .group_by(AgentModel.id, AgentModel.name)
            .order_by(desc(func.count(SessionModel.id)))
        )

        performance = []
        for row in result:
            performance.append({
                "agent_id": row.id,
                "agent_name": row.name,
                "total_sessions": row.total_sessions or 0,
                "avg_session_duration_seconds": float(row.avg_session_duration) if row.avg_session_duration else 0.0,
                "total_messages": row.total_messages or 0,
                "last_active": row.last_active,
            })

        return performance

    async def get_system_health(self) -> Dict[str, Any]:
        """Get system health metrics."""
        # Check for orphaned records
        result = await self.session.execute(
            select(
                func.count(SessionModel.id).filter(SessionModel.persona_id.is_(None)).label("orphaned_sessions"),
                func.count(MessageModel.id).filter(MessageModel.session_id.is_(None)).label("orphaned_messages"),
            )
        )
        orphans = result.first()

        # Check for inactive agents with recent sessions
        recent_cutoff = datetime.utcnow() - timedelta(days=7)
        result = await self.session.execute(
            select(func.count(AgentModel.id))
            .filter(AgentModel.is_active == False)
            .join(SessionModel)
            .where(SessionModel.started_at >= recent_cutoff)
        )
        inactive_with_sessions = result.scalar()

        return {
            "orphaned_sessions": orphans.orphaned_sessions or 0,
            "orphaned_messages": orphans.orphaned_messages or 0,
            "inactive_agents_with_recent_sessions": inactive_with_sessions or 0,
            "health_status": "good" if all([
                orphans.orphaned_sessions == 0,
                orphans.orphaned_messages == 0,
                inactive_with_sessions == 0,
            ]) else "warning",
        }