"""Audit log — traceable record of instructions, decisions, and replies.

Alook uses email as its coordination substrate on purpose: every message
between a human and an agent, or between two agents, lands in an inbox, and
that inbox *is* the audit trail — full accountability, no black boxes.

Persola doesn't need to bolt on real email to get the same property. This
module gives every team/session a chronological, queryable log of who said
what to whom and why, independent of the transient LangGraph/workflow state
that already exists in ``state.WorkflowState``. Think of it as the
non-email inbox: cheap to query, cheap to render as a timeline in the UI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from ..utils.time import utcnow

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import AuditEventType
from ..db.repositories.workqueue_repository import AuditEventRepository
from ._session_store import SessionFactoryMixin


def _utcnow() -> datetime:
    return utcnow()


@dataclass
class AuditEvent:
    event_id: str = field(default_factory=lambda: str(uuid4()))
    team_id: str = "default"
    tenant_id: UUID | None = None
    session_id: str | None = None
    task_id: str | None = None
    event_type: AuditEventType = AuditEventType.INSTRUCTION
    actor: str = "system"  # role or "user"
    recipient: str | None = None  # role this was addressed to, mirrors an email "To:"
    summary: str = ""
    detail: dict[str, Any] = field(default_factory=dict)
    at: datetime = field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "team_id": self.team_id,
            "tenant_id": str(self.tenant_id) if self.tenant_id else None,
            "session_id": self.session_id,
            "task_id": self.task_id,
            "event_type": self.event_type.value,
            "actor": self.actor,
            "recipient": self.recipient,
            "summary": self.summary,
            "detail": self.detail,
            "at": self.at.isoformat(),
        }


def _hydrate_event(row: Any) -> AuditEvent:
    return AuditEvent(
        event_id=row.event_id,
        team_id=row.team_id,
        tenant_id=row.tenant_id if hasattr(row, "tenant_id") else None,
        session_id=row.session_id,
        task_id=row.task_id,
        event_type=AuditEventType(row.event_type),
        actor=row.actor,
        recipient=row.recipient,
        summary=row.summary,
        detail=dict(row.detail or {}),
        at=row.created_at,
    )


class AuditLog(SessionFactoryMixin):
    """DB-backed chronological log of team/session events, stored in ``audit_events``."""

    async def record(
        self,
        *,
        team_id: str,
        event_type: AuditEventType,
        actor: str,
        summary: str,
        recipient: str | None = None,
        session_id: str | None = None,
        task_id: str | None = None,
        detail: dict[str, Any] | None = None,
        tenant_id: UUID | None = None,
        session: AsyncSession | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            team_id=team_id,
            tenant_id=tenant_id,
            session_id=session_id,
            task_id=task_id,
            event_type=event_type,
            actor=actor,
            recipient=recipient,
            summary=summary,
            detail=detail or {},
        )

        async def _op(s: AsyncSession) -> AuditEvent:
            repo = AuditEventRepository(s, tenant_id=tenant_id)
            await repo.create_event(
                event_id=event.event_id,
                team_id=event.team_id,
                event_type=event.event_type.value,
                actor=event.actor,
                summary=event.summary,
                recipient=event.recipient,
                session_id=event.session_id,
                task_id=event.task_id,
                detail=event.detail,
                created_at=event.at,
            )
            return event

        return await self._run(session, _op, commit=True)

    async def timeline(
        self,
        team_id: str,
        *,
        session_id: str | None = None,
        task_id: str | None = None,
        limit: int = 200,
        tenant_id: UUID | None = None,
        session: AsyncSession | None = None,
    ) -> list[dict[str, Any]]:
        async def _op(s: AsyncSession) -> list[dict[str, Any]]:
            repo = AuditEventRepository(s, tenant_id=tenant_id)
            events = [_hydrate_event(row) for row in await repo.timeline(
                team_id, session_id=session_id, task_id=task_id, limit=limit
            )]
            return [e.to_dict() for e in events]

        return await self._run(session, _op, commit=False)


# Process-wide audit log, same singleton pattern as the other orchestration stores.
GLOBAL_AUDIT_LOG = AuditLog()
