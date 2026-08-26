"""Task-queue worker — the async production/productivity path.

Alook's daemon runs on the user's machine, polls its cloud queue, and keeps
agents working after the human has closed their laptop. Persola's
``TeamOrchestrator.run`` is deliberately synchronous (good for interactive
chat), so this module adds the complementary always-on piece: a worker that
polls ``GLOBAL_TASK_QUEUE`` for a team, claims the next queued task,
re-invokes the team on it, and writes the result back — closing the loop
that ``delegate_subtask`` opens.

Usage:
    worker = TaskQueueWorker(team_factory=lambda: TeamOrchestrator(llm_fn=my_llm_fn))
    await worker.run_forever(team_id="default", poll_interval=2.0)

or, for a single production tick (e.g. driven by an API endpoint / cron):
    await worker.tick(team_id="default")
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass

from .audit_log import GLOBAL_AUDIT_LOG, AuditEventType
from .state import TeamSessionState
from .task_queue import GLOBAL_TASK_QUEUE, AgentTask

TeamFactory = Callable[[], "TeamOrchestrator"]  # noqa: F821 - forward ref, avoids circular import


@dataclass
class TickResult:
    claimed: bool
    task: AgentTask | None = None
    error: str | None = None


class TaskQueueWorker:
    """Polls a team's task board and autonomously works queued items."""

    def __init__(self, team_factory: TeamFactory, *, role: str | None = None) -> None:
        self._team_factory = team_factory
        self._role = role  # if set, only claim tasks addressed to this role
        self._stop = asyncio.Event()

    async def tick(self, team_id: str = "default") -> TickResult:
        task = GLOBAL_TASK_QUEUE.claim_next(team_id=team_id, role=self._role)
        if task is None:
            return TickResult(claimed=False)

        GLOBAL_AUDIT_LOG.record(
            team_id=team_id,
            event_type=AuditEventType.STATUS_CHANGE,
            actor=task.role,
            summary=f"claimed task {task.task_id}",
            task_id=task.task_id,
            session_id=task.session_id,
        )
        GLOBAL_TASK_QUEUE.mark_in_progress(task.task_id)

        try:
            orchestrator = self._team_factory()
            session = TeamSessionState(team_id=team_id, session_id=task.session_id or task.task_id)
            result = await orchestrator.run(task.subtask, session=session)
            GLOBAL_TASK_QUEUE.complete(task.task_id, result.response)
            GLOBAL_AUDIT_LOG.record(
                team_id=team_id,
                event_type=AuditEventType.STATUS_CHANGE,
                actor=task.role,
                summary=f"completed task {task.task_id}",
                task_id=task.task_id,
                session_id=session.session_id,
            )
            return TickResult(claimed=True, task=GLOBAL_TASK_QUEUE.get(task.task_id))
        except Exception as exc:  # noqa: BLE001 - surface into the kanban board, don't crash the worker
            GLOBAL_TASK_QUEUE.fail(task.task_id, str(exc))
            GLOBAL_AUDIT_LOG.record(
                team_id=team_id,
                event_type=AuditEventType.STATUS_CHANGE,
                actor=task.role,
                summary=f"failed task {task.task_id}: {exc}",
                task_id=task.task_id,
                session_id=task.session_id,
            )
            return TickResult(
                claimed=True, task=GLOBAL_TASK_QUEUE.get(task.task_id), error=str(exc)
            )

    async def run_forever(self, team_id: str = "default", *, poll_interval: float = 2.0) -> None:
        """Persistent loop, analogous to Alook's always-on local daemon."""
        self._stop.clear()
        while not self._stop.is_set():
            result = await self.tick(team_id)
            await asyncio.sleep(poll_interval if not result.claimed else 0)

    def stop(self) -> None:
        self._stop.set()
