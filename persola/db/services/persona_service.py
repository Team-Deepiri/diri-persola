from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import PersonaModel
from ..repositories import PersonaRepository


class PersonaService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = PersonaRepository(session)

    async def get(self, persona_id: UUID) -> PersonaModel | None:
        return await self.repository.get(persona_id)

    async def create(self, data: dict) -> PersonaModel:
        return await self.repository.create(PersonaModel(**data))

    async def update(self, persona_id: UUID, data: dict) -> PersonaModel | None:
        return await self.repository.update(persona_id, data)

    async def delete(self, persona_id: UUID) -> bool:
        return await self.repository.delete(persona_id)
