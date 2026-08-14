"""Agent task queue — kanban-style, autonomous pickup.

Alook's mechanism: a task assigned at the top of the org chart is written
to a durable ``agentTaskQueue`` row, and agents pick up work, update status,
and close it out on their own — decoupled from any single synchronous call.

Persola's ``TeamOrchestrator.run`` is currently a blocking request/response:
submit a task, wait for the whole team to finish, get one answer back. That
works for interactive chat but not for background/production workloads
(e.g. "keep triaging the inbox", "review every PR opened today"). This
module adds the missing async layer: an in-process queue with kanban
columns (queued -> claimed -> in_progress -> done/failed/blocked) that a
worker (see ``daemon.py``) can poll the way Alook's CLI daemon polls its
cloud queue.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TaskStatus(str, Enum):
    QUEUED = "queued"
    CLAIMED = "claimed"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"
    FAILED = "failed"


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


class AgentTaskQueue:
    """In-process kanban queue, one board per ``team_id``.

    Swap the storage for a DB table later (mirrors Alook's D1-backed
    ``agentTaskQueue``) without changing the public interface — everything
    reads/writes through ``enqueue`` / ``claim_next`` / ``complete`` / ``fail``.
    """

    def __init__(self) -> None:
        self._tasks: Dict[str, AgentTask] = {}

    def enqueue(
        self,
        *,
        team_id: str,
        role: str,
        subtask: str,
        origin: str = "user",
        parent_task_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> AgentTask:
        task = AgentTask(
            team_id=team_id,
            role=role,
            subtask=subtask,
            origin=origin,
            parent_task_id=parent_task_id,
            session_id=session_id,
        )
        self._tasks[task.task_id] = task
        return task

    def claim_next(self, *, team_id: str, role: Optional[str] = None) -> Optional[AgentTask]:
        """Autonomous pickup: the next queued task for this team (optionally a specific role)."""
        for task in sorted(self._tasks.values(), key=lambda t: t.created_at):
            if task.team_id != team_id or task.status != TaskStatus.QUEUED:
                continue
            if role is not None and task.role != role:
                continue
            task.status = TaskStatus.CLAIMED
            task.claimed_at = _utcnow()
            return task
        return None

    def mark_in_progress(self, task_id: str) -> Optional[AgentTask]:
        task = self._tasks.get(task_id)
        if task:
            task.status = TaskStatus.IN_PROGRESS
        return task

    def block(self, task_id: str, reason: str) -> Optional[AgentTask]:
        task = self._tasks.get(task_id)
        if task:
            task.status = TaskStatus.BLOCKED
            task.error = reason
        return task

    def complete(self, task_id: str, result: str) -> Optional[AgentTask]:
        task = self._tasks.get(task_id)
        if task:
            task.status = TaskStatus.DONE
            task.result = result
            task.completed_at = _utcnow()
        return task

    def fail(self, task_id: str, error: str) -> Optional[AgentTask]:
        task = self._tasks.get(task_id)
        if task:
            task.status = TaskStatus.FAILED
            task.error = error
            task.completed_at = _utcnow()
        return task

    def get(self, task_id: str) -> Optional[AgentTask]:
        return self._tasks.get(task_id)

    def board(self, team_id: str) -> Dict[str, List[Dict[str, Any]]]:
        """Kanban view: tasks grouped by column, newest first within each column."""
        columns: Dict[str, List[Dict[str, Any]]] = {s.value: [] for s in TaskStatus}
        for task in sorted(self._tasks.values(), key=lambda t: t.created_at, reverse=True):
            if task.team_id == team_id:
                columns[task.status.value].append(task.to_dict())
        return columns

    def children(self, parent_task_id: str) -> List[AgentTask]:
        return [t for t in self._tasks.values() if t.parent_task_id == parent_task_id]


# Process-wide queue, same singleton pattern as GLOBAL_MEMORY / GLOBAL_ORG_CHART.
GLOBAL_TASK_QUEUE = AgentTaskQueue()
