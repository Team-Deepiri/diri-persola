"""Repositories for communal city — families, jobs, commons, events."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import (
    CityEventModel,
    CityJobModel,
    FamilyMemberModel,
    FamilyModel,
    WorkspaceArtifactModel,
    WorkspaceRunModel,
)
from .base import BaseRepository


class FamilyRepository(BaseRepository[FamilyModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, FamilyModel)

    async def get_with_members(self, family_id: UUID) -> FamilyModel | None:
        from ..models import AgentModel

        query = (
            select(FamilyModel)
            .where(FamilyModel.id == family_id)
            .options(
                selectinload(FamilyModel.members)
                .selectinload(FamilyMemberModel.agent)
                .selectinload(AgentModel.persona),
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_recent(self, limit: int = 50) -> list[FamilyModel]:
        query = (
            select(FamilyModel)
            .where(FamilyModel.is_active.is_(True))
            .order_by(FamilyModel.updated_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())


class FamilyMemberRepository(BaseRepository[FamilyMemberModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, FamilyMemberModel)

    async def list_for_family(self, family_id: UUID) -> list[FamilyMemberModel]:
        query = (
            select(FamilyMemberModel)
            .where(FamilyMemberModel.family_id == family_id)
            .options(selectinload(FamilyMemberModel.agent))
            .order_by(FamilyMemberModel.created_at.asc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_parent(self, family_id: UUID) -> FamilyMemberModel | None:
        query = (
            select(FamilyMemberModel)
            .where(
                FamilyMemberModel.family_id == family_id,
                FamilyMemberModel.role_in_family == "parent",
                FamilyMemberModel.life_status == "alive",
                FamilyMemberModel.is_active.is_(True),
            )
            .options(selectinload(FamilyMemberModel.agent))
        )
        result = await self.session.execute(query)
        parent = result.scalar_one_or_none()
        if parent is not None:
            return parent
        # Fallback: any parent row (including deceased) for lineage attachment
        query = (
            select(FamilyMemberModel)
            .where(
                FamilyMemberModel.family_id == family_id,
                FamilyMemberModel.role_in_family == "parent",
            )
            .options(selectinload(FamilyMemberModel.agent))
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()


class CityJobRepository(BaseRepository[CityJobModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CityJobModel)

    async def list_for_family(self, family_id: UUID, limit: int = 50) -> list[CityJobModel]:
        query = (
            select(CityJobModel)
            .where(CityJobModel.family_id == family_id)
            .order_by(CityJobModel.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())


class WorkspaceArtifactRepository(BaseRepository[WorkspaceArtifactModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, WorkspaceArtifactModel)

    async def list_for_job(self, job_id: UUID, limit: int = 200) -> list[WorkspaceArtifactModel]:
        query = (
            select(WorkspaceArtifactModel)
            .where(WorkspaceArtifactModel.job_id == job_id)
            .order_by(WorkspaceArtifactModel.path.asc(), WorkspaceArtifactModel.version.desc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_latest_by_path(self, job_id: UUID, path: str) -> WorkspaceArtifactModel | None:
        query = (
            select(WorkspaceArtifactModel)
            .where(
                WorkspaceArtifactModel.job_id == job_id,
                WorkspaceArtifactModel.path == path,
            )
            .order_by(WorkspaceArtifactModel.version.desc())
            .limit(1)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def latest_version(self, job_id: UUID, path: str) -> int:
        query = (
            select(WorkspaceArtifactModel.version)
            .where(
                WorkspaceArtifactModel.job_id == job_id,
                WorkspaceArtifactModel.path == path,
            )
            .order_by(WorkspaceArtifactModel.version.desc())
            .limit(1)
        )
        result = await self.session.execute(query)
        value = result.scalar_one_or_none()
        return int(value) if value is not None else 0


class WorkspaceRunRepository(BaseRepository[WorkspaceRunModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, WorkspaceRunModel)

    async def list_for_job(self, job_id: UUID, limit: int = 200) -> list[WorkspaceRunModel]:
        query = (
            select(WorkspaceRunModel)
            .where(WorkspaceRunModel.job_id == job_id)
            .order_by(WorkspaceRunModel.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())


class CityEventRepository(BaseRepository[CityEventModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CityEventModel)

    async def list_for_job(self, job_id: UUID, limit: int = 500) -> list[CityEventModel]:
        query = (
            select(CityEventModel)
            .where(CityEventModel.job_id == job_id)
            .order_by(CityEventModel.created_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def list_for_family(self, family_id: UUID, limit: int = 500) -> list[CityEventModel]:
        query = (
            select(CityEventModel)
            .where(CityEventModel.family_id == family_id)
            .order_by(CityEventModel.created_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def list_recent(self, limit: int = 100) -> list[CityEventModel]:
        """City-wide recent events (newest first) for snapshot viz."""
        query = select(CityEventModel).order_by(CityEventModel.created_at.desc()).limit(limit)
        result = await self.session.execute(query)
        rows = list(result.scalars().all())
        rows.reverse()  # chronological for feed consumers
        return rows

    async def list_since(
        self,
        *,
        family_id: UUID | None = None,
        job_id: UUID | None = None,
        after_id: UUID | None = None,
        since: datetime | None = None,
        event_types: list[str] | None = None,
        limit: int = 100,
    ) -> list[CityEventModel]:
        filters = []
        if family_id is not None:
            filters.append(CityEventModel.family_id == family_id)
        if job_id is not None:
            filters.append(CityEventModel.job_id == job_id)
        if event_types:
            filters.append(CityEventModel.event_type.in_(list(event_types)))
        if after_id is not None:
            anchor = await self.get(after_id)
            if anchor is not None:
                filters.append(
                    or_(
                        CityEventModel.created_at > anchor.created_at,
                        and_(
                            CityEventModel.created_at == anchor.created_at,
                            CityEventModel.id > anchor.id,
                        ),
                    )
                )
        elif since is not None:
            filters.append(CityEventModel.created_at > since)

        query = select(CityEventModel)
        if filters:
            query = query.where(and_(*filters))
        query = query.order_by(CityEventModel.created_at.asc(), CityEventModel.id.asc()).limit(
            limit
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())
