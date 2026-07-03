"""Persisted team orchestration — DB + Redis memory."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import TeamSessionModel, TeamWorkflowModel, TeamWorkflowStatus
from ..db.repositories.team_repository import (
    TeamMemoryRepository,
    TeamSessionRepository,
    TeamWorkflowRepository,
    TeamWorkflowStepRepository,
)
from ..models import PersonaProfile
from ..orchestration.redis_memory import REDIS_TEAM_MEMORY
from ..orchestration.state import TeamSessionState, WorkflowState
from ..orchestration.team import TeamOrchestrator, TeamRunResult
from ..orchestration.tool_loader import build_team_registry

LLMFn = Callable[[str, str], Awaitable[str]]


class TeamService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.sessions = TeamSessionRepository(db)
        self.workflows = TeamWorkflowRepository(db)
        self.steps = TeamWorkflowStepRepository(db)
        self.memory = TeamMemoryRepository(db)

    async def _resolve_or_create_session(
        self,
        *,
        external_session_id: str | None,
        persona_id: UUID | None,
        team_config: dict | None,
    ) -> tuple[TeamSessionModel, TeamSessionState]:
        runtime = TeamSessionState(session_id=external_session_id or TeamSessionState().session_id)
        row = await self.sessions.get_by_external_id(runtime.session_id)
        if row is None:
            row = TeamSessionModel(
                external_session_id=runtime.session_id,
                persona_id=persona_id,
                team_config=team_config or {},
            )
            row = await self.sessions.create(row)
        elif persona_id and row.persona_id != persona_id:
            row.persona_id = persona_id
            await self.db.flush()

        redis_snapshot = await REDIS_TEAM_MEMORY.snapshot(runtime.session_id)
        if redis_snapshot:
            runtime.memory_snapshot = redis_snapshot
        elif row.memory_snapshot:
            runtime.memory_snapshot = row.memory_snapshot

        return row, runtime

    async def invoke(
        self,
        task: str,
        *,
        llm_fn: LLMFn,
        persona_profile: PersonaProfile | None = None,
        session_id: str | None = None,
        persona_id: UUID | None = None,
        agent_id: UUID | None = None,
        use_langgraph: bool = True,
    ) -> TeamRunResult:
        session_row, runtime = await self._resolve_or_create_session(
            external_session_id=session_id,
            persona_id=persona_id,
            team_config={"use_langgraph": use_langgraph},
        )

        registry = await build_team_registry(runtime.session_id, db=self.db, agent_id=agent_id)
        orchestrator = TeamOrchestrator(
            llm_fn=llm_fn,
            persona_profile=persona_profile,
            tool_registry=registry,
            use_langgraph=use_langgraph,
        )

        workflow_row = TeamWorkflowModel(
            team_session_id=session_row.id,
            goal=task,
            status=TeamWorkflowStatus.RUNNING.value,
        )
        workflow_row = await self.workflows.create(workflow_row)

        result = await orchestrator.run(task, session=runtime)
        await self._persist_run(session_row, workflow_row, result)
        return result

    async def _persist_run(
        self,
        session_row: TeamSessionModel,
        workflow_row: TeamWorkflowModel,
        result: TeamRunResult,
    ) -> None:
        step_order = 0
        for step in result.workflow.steps:
            await self.steps.add_step(
                workflow_id=workflow_row.id,
                step_order=step_order,
                role=step.role,
                task=step.task,
                output=step.output,
                tool_calls=step.tool_calls,
                parallel_group=step.tool_calls[0].get("parallel_group") if step.tool_calls else None,
            )
            step_order += 1
            await self.memory.upsert_entry(
                team_session_id=session_row.id,
                memory_key=f"{step.role}:latest",
                value=step.output[:4000],
                tags=["workflow", step.role],
                source_role=step.role,
            )

        redis_snapshot = await REDIS_TEAM_MEMORY.snapshot(result.session_id)
        session_row.memory_snapshot = redis_snapshot or result.session.memory_snapshot
        await self.sessions.increment_messages(session_row.id, count=2)

        await self.workflows.mark_completed(
            workflow_row.id,
            final_response=result.response,
            personalities_used=result.personalities_used,
            tool_results=result.tool_results,
            delegation_plan=result.delegation_plan,
        )
        await self.db.commit()

    async def get_session_detail(self, external_session_id: str) -> dict[str, Any] | None:
        row = await self.sessions.get_with_workflows(external_session_id)
        if row is None:
            return None

        redis_memory = await REDIS_TEAM_MEMORY.snapshot(external_session_id)
        workflows = await self.workflows.list_for_session(row.id)
        memory_rows = await self.memory.list_for_session(row.id)

        return {
            "session_id": row.external_session_id,
            "name": row.name,
            "persona_id": str(row.persona_id) if row.persona_id else None,
            "message_count": row.message_count,
            "team_config": row.team_config,
            "memory_snapshot": redis_memory or row.memory_snapshot,
            "memory_entries": [
                {
                    "key": m.memory_key,
                    "value": m.value,
                    "tags": m.tags,
                    "source_role": m.source_role,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in memory_rows
            ],
            "workflows": [
                {
                    "id": str(w.id),
                    "goal": w.goal,
                    "status": w.status,
                    "final_response": w.final_response,
                    "personalities_used": w.personalities_used,
                    "delegation_plan": w.delegation_plan,
                    "tool_results": w.tool_results,
                    "created_at": w.created_at.isoformat() if w.created_at else None,
                    "completed_at": w.completed_at.isoformat() if w.completed_at else None,
                    "steps": [
                        {
                            "role": s.role,
                            "task": s.task,
                            "output": s.output,
                            "tool_calls": s.tool_calls,
                            "parallel_group": s.parallel_group,
                            "duration_ms": s.duration_ms,
                        }
                        for s in sorted(w.steps, key=lambda x: x.step_order)
                    ],
                }
                for w in workflows
            ],
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

    async def list_sessions(self, limit: int = 25) -> list[dict[str, Any]]:
        rows = await self.sessions.list_recent(limit=limit)
        return [
            {
                "session_id": r.external_session_id,
                "name": r.name,
                "message_count": r.message_count,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in rows
        ]

    async def search_memory(self, external_session_id: str, query: str) -> list[dict[str, Any]]:
        redis_hits = await REDIS_TEAM_MEMORY.search(external_session_id, query)
        if redis_hits:
            return redis_hits

        row = await self.sessions.get_by_external_id(external_session_id)
        if row is None:
            return []

        entries = await self.memory.list_for_session(row.id)
        query_lower = query.lower()
        hits: list[dict[str, Any]] = []
        for entry in entries:
            haystack = f"{entry.memory_key} {entry.value} {' '.join(entry.tags)}".lower()
            if query_lower in haystack:
                hits.append(
                    {
                        "key": entry.memory_key,
                        "value": entry.value,
                        "tags": entry.tags,
                        "source_role": entry.source_role,
                    }
                )
        return hits
