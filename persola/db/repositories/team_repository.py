from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import TeamMemoryModel, TeamSessionModel, TeamWorkflowModel, TeamWorkflowStepModel, TeamWorkflowStatus
from .base import BaseRepository


class TeamSessionRepository(BaseRepository[TeamSessionModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TeamSessionModel)

    async def get_by_external_id(self, external_session_id: str) -> TeamSessionModel | None:
        query = select(TeamSessionModel).where(TeamSessionModel.external_session_id == external_session_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_with_workflows(self, external_session_id: str) -> TeamSessionModel | None:
        query = (
            select(TeamSessionModel)
            .where(TeamSessionModel.external_session_id == external_session_id)
            .options(selectinload(TeamSessionModel.workflows).selectinload(TeamWorkflowModel.steps))
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_recent(self, limit: int = 25) -> list[TeamSessionModel]:
        query = select(TeamSessionModel).order_by(TeamSessionModel.updated_at.desc()).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def increment_messages(self, item_id: UUID, count: int = 1) -> None:
        item = await self.get(item_id)
        if item is None:
            return
        item.message_count += count
        await self.session.flush()


class TeamWorkflowRepository(BaseRepository[TeamWorkflowModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TeamWorkflowModel)

    async def list_for_session(self, team_session_id: UUID, limit: int = 20) -> list[TeamWorkflowModel]:
        query = (
            select(TeamWorkflowModel)
            .where(TeamWorkflowModel.team_session_id == team_session_id)
            .options(selectinload(TeamWorkflowModel.steps))
            .order_by(TeamWorkflowModel.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_with_steps(self, workflow_id: UUID) -> TeamWorkflowModel | None:
        query = (
            select(TeamWorkflowModel)
            .where(TeamWorkflowModel.id == workflow_id)
            .options(selectinload(TeamWorkflowModel.steps))
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def mark_completed(
        self,
        workflow_id: UUID,
        *,
        final_response: str,
        personalities_used: list[str],
        tool_results: list,
        delegation_plan: dict,
    ) -> TeamWorkflowModel | None:
        item = await self.get(workflow_id)
        if item is None:
            return None
        item.status = TeamWorkflowStatus.COMPLETED.value
        item.final_response = final_response
        item.personalities_used = personalities_used
        item.tool_results = tool_results
        item.delegation_plan = delegation_plan
        item.completed_at = datetime.utcnow()
        await self.session.flush()
        await self.session.refresh(item)
        return item


class TeamMemoryRepository(BaseRepository[TeamMemoryModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TeamMemoryModel)

    async def list_for_session(self, team_session_id: UUID, limit: int = 100) -> list[TeamMemoryModel]:
        query = (
            select(TeamMemoryModel)
            .where(TeamMemoryModel.team_session_id == team_session_id)
            .order_by(TeamMemoryModel.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def upsert_entry(
        self,
        *,
        team_session_id: UUID,
        memory_key: str,
        value: str,
        tags: list[str] | None = None,
        source_role: str | None = None,
    ) -> TeamMemoryModel:
        query = select(TeamMemoryModel).where(
            TeamMemoryModel.team_session_id == team_session_id,
            TeamMemoryModel.memory_key == memory_key,
        )
        result = await self.session.execute(query)
        existing = result.scalar_one_or_none()
        if existing is not None:
            existing.value = value
            existing.tags = tags or []
            existing.source_role = source_role
            await self.session.flush()
            await self.session.refresh(existing)
            return existing

        entry = TeamMemoryModel(
            team_session_id=team_session_id,
            memory_key=memory_key,
            value=value,
            tags=tags or [],
            source_role=source_role,
        )
        return await self.create(entry)


class TeamWorkflowStepRepository(BaseRepository[TeamWorkflowStepModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TeamWorkflowStepModel)

    async def add_step(
        self,
        *,
        workflow_id: UUID,
        step_order: int,
        role: str,
        task: str,
        output: str,
        tool_calls: list | None = None,
        parallel_group: str | None = None,
        duration_ms: int | None = None,
    ) -> TeamWorkflowStepModel:
        step = TeamWorkflowStepModel(
            workflow_id=workflow_id,
            step_order=step_order,
            role=role,
            task=task,
            output=output,
            tool_calls=tool_calls or [],
            parallel_group=parallel_group,
            duration_ms=duration_ms,
        )
        return await self.create(step)
