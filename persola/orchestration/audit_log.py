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
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuditEventType(str, Enum):
    INSTRUCTION = "instruction"  # a task/subtask was assigned to a role
    DECISION = "decision"  # a role produced output that changes what happens next
    REPLY = "reply"  # a role replied to whoever assigned the work
    STATUS_CHANGE = "status_change"  # kanban column change on an AgentTask
    TOOL_CALL = "tool_call"


@dataclass
class AuditEvent:
    event_id: str = field(default_factory=lambda: str(uuid4()))
    team_id: str = "default"
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
            "session_id": self.session_id,
            "task_id": self.task_id,
            "event_type": self.event_type.value,
            "actor": self.actor,
            "recipient": self.recipient,
            "summary": self.summary,
            "detail": self.detail,
            "at": self.at.isoformat(),
        }


class AuditLog:
    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    def record(
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
    ) -> AuditEvent:
        event = AuditEvent(
            team_id=team_id,
            session_id=session_id,
            task_id=task_id,
            event_type=event_type,
            actor=actor,
            recipient=recipient,
            summary=summary,
            detail=detail or {},
        )
        self._events.append(event)
        return event

    def timeline(
        self,
        team_id: str,
        *,
        session_id: str | None = None,
        task_id: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        events = [e for e in self._events if e.team_id == team_id]
        if session_id is not None:
            events = [e for e in events if e.session_id == session_id]
        if task_id is not None:
            events = [e for e in events if e.task_id == task_id]
        events.sort(key=lambda e: e.at)
        return [e.to_dict() for e in events[-limit:]]


# Process-wide audit log, same singleton pattern as the other orchestration stores.
GLOBAL_AUDIT_LOG = AuditLog()
