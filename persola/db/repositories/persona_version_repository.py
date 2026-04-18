from __future__ import annotations

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import PersonaVersionModel
from .base import BaseRepository


class PersonaVersionRepository(BaseRepository[PersonaVersionModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, PersonaVersionModel)

    async def get_latest_version_number(self, persona_id) -> int:
        query = select(func.max(PersonaVersionModel.version_number)).where(PersonaVersionModel.persona_id == persona_id)
        result = await self.session.execute(query)
        latest = result.scalar_one_or_none()
        return int(latest or 0)

    async def list_by_persona(self, persona_id, limit: int = 50) -> list[PersonaVersionModel]:
        query = (
            select(PersonaVersionModel)
            .where(PersonaVersionModel.persona_id == persona_id)
            .order_by(desc(PersonaVersionModel.version_number))
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())