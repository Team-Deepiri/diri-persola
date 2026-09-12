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
import time
from dataclasses import dataclass
from typing import Callable, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import CityEventModel
from ..metrics import observe_workqueue_task_duration, record_workqueue_task
from ._session_store import SessionFactoryMixin
from .audit_log import AuditEventType, GLOBAL_AUDIT_LOG
from .state import TeamSessionState
from .task_queue import GLOBAL_TASK_QUEUE, AgentTask, TaskStatus

TeamFactory = Callable[[], "TeamOrchestrator"]  # noqa: F821 - forward ref, avoids circular import


@dataclass
class TickResult:
    claimed: bool
    task: Optional[AgentTask] = None
    error: Optional[str] = None


def _record_city_event(
    session: AsyncSession,
    task: AgentTask,
    outcome: str,
    *,
    result: Optional[str] = None,
    error: Optional[str] = None,
) -> None:
    payload = {
        "task_id": task.task_id,
        "team_id": task.team_id,
        "role": task.role,
        "subtask": task.subtask[:500],
    }
    if result is not None:
        payload["result"] = result[:1000]
    if error is not None:
        payload["error"] = error[:1000]
    session.add(
        CityEventModel(
            family_id=None,
            job_id=None,
            event_type=f"workqueue.task.{outcome}",
            payload=payload,
        )
    )


class TaskQueueWorker(SessionFactoryMixin):
    """Polls a team's task board and autonomously works queued items."""

    def __init__(self, team_factory: TeamFactory, *, role: Optional[str] = None) -> None:
        self._team_factory = team_factory
        self._role = role  # if set, only claim tasks addressed to this role
        self._stop = asyncio.Event()
        # Persist to the same database the task queue uses (None -> AsyncSessionLocal).
        self.set_session_factory(GLOBAL_TASK_QUEUE._session_factory)

    async def tick(
        self, team_id: str = "default", *, session: Optional[AsyncSession] = None
    ) -> TickResult:
        if session is not None:
            return await self._tick(team_id, session)
        async with self._open_session() as opened:
            return await self._tick(team_id, opened)

    async def _tick(self, team_id: str, session: AsyncSession) -> TickResult:
        started = time.perf_counter()
        task = await GLOBAL_TASK_QUEUE.claim_next(team_id=team_id, role=self._role, session=session)
        if task is None:
            return TickResult(claimed=False)

        await GLOBAL_AUDIT_LOG.record(
            team_id=team_id,
            event_type=AuditEventType.STATUS_CHANGE,
            actor=task.role,
            summary=f"claimed task {task.task_id}",
            task_id=task.task_id,
            session_id=task.session_id,
            session=session,
        )
        await GLOBAL_TASK_QUEUE.mark_in_progress(task.task_id, session=session)

        try:
            orchestrator = self._team_factory()
            session_state = TeamSessionState(
                team_id=team_id, session_id=task.session_id or task.task_id
            )
            result = await orchestrator.run(task.subtask, session=session_state)
            await GLOBAL_TASK_QUEUE.complete(task.task_id, result.response, session=session)
            await GLOBAL_AUDIT_LOG.record(
                team_id=team_id,
                event_type=AuditEventType.STATUS_CHANGE,
                actor=task.role,
                summary=f"completed task {task.task_id}",
                task_id=task.task_id,
                session_id=session_state.session_id,
                session=session,
            )
            _record_city_event(session, task, "completed", result=result.response)
            await session.commit()
            record_workqueue_task("done")
            observe_workqueue_task_duration(time.perf_counter() - started)
            return TickResult(
                claimed=True, task=await GLOBAL_TASK_QUEUE.get(task.task_id, session=session)
            )
        except Exception as exc:  # noqa: BLE001 - surface into the kanban board, don't crash the worker
            await GLOBAL_TASK_QUEUE.fail(task.task_id, str(exc), session=session)
            await GLOBAL_AUDIT_LOG.record(
                team_id=team_id,
                event_type=AuditEventType.STATUS_CHANGE,
                actor=task.role,
                summary=f"failed task {task.task_id}: {exc}",
                task_id=task.task_id,
                session_id=task.session_id,
                session=session,
            )
            _record_city_event(session, task, "failed", error=str(exc))
            await session.commit()
            record_workqueue_task("failed")
            observe_workqueue_task_duration(time.perf_counter() - started)
            return TickResult(
                claimed=True,
                task=await GLOBAL_TASK_QUEUE.get(task.task_id, session=session),
                error=str(exc),
            )

    async def run_forever(
        self,
        team_id: str = "default",
        *,
        poll_interval: float = 2.0,
        available_check: Optional[Callable[[], bool]] = None,
    ) -> None:
        """Persistent loop, analogous to Alook's always-on local daemon.

        ``available_check`` (e.g. "is the LLM reachable?") gates task claims —
        without it the worker would claim-and-fail every task while the model
        provider is down.
        """
        self._stop.clear()
        while not self._stop.is_set():
            if available_check is not None and not available_check():
                await asyncio.sleep(poll_interval)
                continue
            result = await self.tick(team_id)
            await asyncio.sleep(poll_interval if not result.claimed else 0)

    def stop(self) -> None:
        self._stop.set()
