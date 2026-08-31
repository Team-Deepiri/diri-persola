"""Agent task queue — kanban-style, autonomous pickup.

Alook's mechanism: a task assigned at the top of the org chart is written
to a durable ``agentTaskQueue`` row, and agents pick up work, update status,
and close it out on their own — decoupled from any single synchronous call.

Persola's ``TeamOrchestrator.run`` is currently a blocking request/response:
submit a task, wait for the whole team to finish, get one answer back. That
works for interactive chat but not for background/production workloads
(e.g. "keep triaging the inbox", "review every PR opened today"). This
module adds the missing async layer: a durable DB-backed queue with kanban
columns (queued -> claimed -> in_progress -> done/failed/blocked) that a
worker (see ``daemon.py``) can poll the way Alook's CLI daemon polls its
cloud queue.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import WorkTaskStatus as TaskStatus
from ..db.repositories.workqueue_repository import WorkTaskRepository
from ._session_store import SessionFactoryMixin


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class AgentTask:
    task_id: str = field(default_factory=lambda: str(uuid4()))
    team_id: str = "default"
    role: str = "coordinator"  # who this is assigned to, per the org chart
    subtask: str = ""
    origin: str = "user"  # "user" | role that delegated it | "schedule"
    status: TaskStatus = TaskStatus.QUEUED
    result: Optional[str] = None
    error: Optional[str] = None
    parent_task_id: Optional[str] = None
    session_id: Optional[str] = None
    created_at: datetime = field(default_factory=_utcnow)
    claimed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "team_id": self.team_id,
            "role": self.role,
            "subtask": self.subtask,
            "origin": self.origin,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "parent_task_id": self.parent_task_id,
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "claimed_at": self.claimed_at.isoformat() if self.claimed_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


def _hydrate_task(row: Any) -> AgentTask:
    return AgentTask(
        task_id=row.task_id,
        team_id=row.team_id,
        role=row.role,
        subtask=row.subtask,
        origin=row.origin,
        status=TaskStatus(row.status),
        result=row.result,
        error=row.error,
        parent_task_id=row.parent_task_id,
        session_id=row.session_id,
        created_at=row.created_at,
        claimed_at=row.claimed_at,
        completed_at=row.completed_at,
    )


class AgentTaskQueue(SessionFactoryMixin):
    """DB-backed kanban queue, one board per ``team_id``.

    Public interface (``enqueue`` / ``claim_next`` / ``complete`` / ``fail``)
    is unchanged from the in-memory version; storage now lives in ``work_tasks``.
    Every method accepts an optional ``session`` — when provided the caller owns
    the transaction; otherwise a session is opened from the injected factory
    (``AsyncSessionLocal`` in production) and committed.
    """

    async def enqueue(
        self,
        *,
        team_id: str,
        role: str,
        subtask: str,
        origin: str = "user",
        parent_task_id: Optional[str] = None,
        session_id: Optional[str] = None,
        session: Optional[AsyncSession] = None,
    ) -> AgentTask:
        task = AgentTask(
            team_id=team_id,
            role=role,
            subtask=subtask,
            origin=origin,
            parent_task_id=parent_task_id,
            session_id=session_id,
        )

        async def _op(s: AsyncSession) -> AgentTask:
            repo = WorkTaskRepository(s)
            await repo.create_task(
                task_id=task.task_id,
                team_id=task.team_id,
                role=task.role,
                subtask=task.subtask,
                origin=task.origin,
                status=TaskStatus.QUEUED.value,
                parent_task_id=task.parent_task_id,
                session_id=task.session_id,
            )
            return task

        return await self._run(session, _op, commit=True)

    async def claim_next(
        self,
        *,
        team_id: str,
        role: Optional[str] = None,
        session: Optional[AsyncSession] = None,
    ) -> Optional[AgentTask]:
        """Autonomous pickup: the next queued task for this team (optionally a specific role)."""

        async def _op(s: AsyncSession) -> Optional[AgentTask]:
            repo = WorkTaskRepository(s)
            row = await repo.claim_next(team_id, role)
            return _hydrate_task(row) if row is not None else None

        return await self._run(session, _op, commit=True)

    async def mark_in_progress(
        self, task_id: str, *, session: Optional[AsyncSession] = None
    ) -> Optional[AgentTask]:
        return await self._set_status(task_id, TaskStatus.IN_PROGRESS, session=session)

    async def block(
        self, task_id: str, reason: str, *, session: Optional[AsyncSession] = None
    ) -> Optional[AgentTask]:
        return await self._set_status(task_id, TaskStatus.BLOCKED, error=reason, session=session)

    async def complete(
        self, task_id: str, result: str, *, session: Optional[AsyncSession] = None
    ) -> Optional[AgentTask]:
        return await self._set_status(
            task_id, TaskStatus.DONE, result=result, mark_completed=True, session=session
        )

    async def fail(
        self, task_id: str, error: str, *, session: Optional[AsyncSession] = None
    ) -> Optional[AgentTask]:
        return await self._set_status(
            task_id, TaskStatus.FAILED, error=error, mark_completed=True, session=session
        )

    async def _set_status(
        self,
        task_id: str,
        status: TaskStatus,
        *,
        result: Optional[str] = None,
        error: Optional[str] = None,
        mark_completed: bool = False,
        session: Optional[AsyncSession] = None,
    ) -> Optional[AgentTask]:
        async def _op(s: AsyncSession) -> Optional[AgentTask]:
            repo = WorkTaskRepository(s)
            row = await repo.update_status(
                task_id,
                status.value,
                result=result,
                error=error,
                mark_completed=mark_completed,
            )
            return _hydrate_task(row) if row is not None else None

        return await self._run(session, _op, commit=True)

    async def get(
        self, task_id: str, *, session: Optional[AsyncSession] = None
    ) -> Optional[AgentTask]:
        async def _op(s: AsyncSession) -> Optional[AgentTask]:
            repo = WorkTaskRepository(s)
            row = await repo.get_by_task_id(task_id)
            return _hydrate_task(row) if row is not None else None

        return await self._run(session, _op, commit=False)

    async def board(
        self, team_id: str, *, session: Optional[AsyncSession] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Kanban view: tasks grouped by column, newest first within each column."""
        async def _op(s: AsyncSession) -> Dict[str, List[Dict[str, Any]]]:
            repo = WorkTaskRepository(s)
            tasks = [_hydrate_task(row) for row in await repo.list_for_team(team_id)]
            columns: Dict[str, List[Dict[str, Any]]] = {status.value: [] for status in TaskStatus}
            for task in sorted(tasks, key=lambda t: t.created_at, reverse=True):
                columns[task.status.value].append(task.to_dict())
            return columns

        return await self._run(session, _op, commit=False)

    async def children(
        self, parent_task_id: str, *, session: Optional[AsyncSession] = None
    ) -> List[AgentTask]:
        async def _op(s: AsyncSession) -> List[AgentTask]:
            repo = WorkTaskRepository(s)
            return [_hydrate_task(row) for row in await repo.children(parent_task_id)]

        return await self._run(session, _op, commit=False)


# Process-wide queue, same singleton pattern as GLOBAL_MEMORY / GLOBAL_ORG_CHART.
GLOBAL_TASK_QUEUE = AgentTaskQueue()
