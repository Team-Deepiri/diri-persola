from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AnalysisRunModel
from .base import BaseRepository


class AnalysisRunRepository(BaseRepository[AnalysisRunModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AnalysisRunModel)

    async def list_recent(self, limit: int = 50) -> list[AnalysisRunModel]:
        query = select(AnalysisRunModel).order_by(desc(AnalysisRunModel.created_at)).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())