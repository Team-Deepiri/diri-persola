from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ...cache import PersonaCache
from ...engine import PersonaEngine
from ..models import PersonaModel
from ..repositories import PersonaRepository


class PersonaService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = PersonaRepository(session)
        self.engine = PersonaEngine()
        self.cache = PersonaCache()

    async def get(self, persona_id: UUID) -> PersonaModel | None:
        return await self.repository.get(persona_id)

    async def create(self, data: dict) -> PersonaModel:
        return await self.repository.create(PersonaModel(**data))

    async def update(self, persona_id: UUID, data: dict) -> PersonaModel | None:
        updated = await self.repository.update(persona_id, data)
        if updated is not None:
            await self.cache.invalidate(persona_id)
        return updated

    async def delete(self, persona_id: UUID) -> bool:
        deleted = await self.repository.delete(persona_id)
        if deleted:
            await self.cache.invalidate(persona_id)
        return deleted

    async def get_system_prompt(self, persona_id: UUID) -> str | None:
        cached = await self.cache.get_system_prompt(persona_id)
        if cached is not None:
            return cached

        persona = await self.get(persona_id)
        if persona is None:
            return None

        prompt = self.engine.build_system_prompt(persona.to_profile())
        await self.cache.set_system_prompt(persona_id, prompt)
        return prompt

    async def get_sampling_params(self, persona_id: UUID) -> dict[str, Any] | None:
        cached = await self.cache.get_sampling(persona_id)
        if cached is not None:
            return cached

        persona = await self.get(persona_id)
        if persona is None:
            return None

        params = self.engine.get_sampling_params(persona.to_profile())
        await self.cache.set_sampling(persona_id, params)
        return params
