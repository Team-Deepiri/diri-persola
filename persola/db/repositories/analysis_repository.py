from __future__ import annotations

from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AnalysisRunModel
from .base import BaseRepository


class AnalysisRunRepository(BaseRepository[AnalysisRunModel]):
    def __init__(
        self,
        session: AsyncSession,
        tenant_id: UUID | None = None,
    ) -> None:
        super().__init__(session, AnalysisRunModel, tenant_id=tenant_id)

    async def list_recent(self, limit: int = 50) -> list[AnalysisRunModel]:
        query = self._tenant_filter(
            select(AnalysisRunModel).order_by(desc(AnalysisRunModel.created_at)).limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())