from __future__ import annotations

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import PersonaModel
from .base import BaseRepository


class PersonaRepository(BaseRepository[PersonaModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, PersonaModel)

    async def get_by_name(self, name: str) -> PersonaModel | None:
        query = select(PersonaModel).where(PersonaModel.name == name)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_presets(self) -> list[PersonaModel]:
        query = select(PersonaModel).where(PersonaModel.is_preset.is_(True))
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def search(self, query_text: str) -> list[PersonaModel]:
        term = query_text.strip()
        if not term:
            return []
        query = select(PersonaModel).where(
            or_(
                PersonaModel.name.ilike(f"%{term}%"),
                PersonaModel.description.ilike(f"%{term}%"),
            )
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def clone(self, item_id: UUID, new_name: str) -> PersonaModel:
        original = await self.get(item_id)
        if original is None:
            raise ValueError("Persona not found")

        clone_profile = original.to_profile().model_copy(update={"name": new_name})
        clone = PersonaModel.from_profile(clone_profile, is_preset=False)
        return await self.create(clone)

    async def seed_presets(self, presets: dict) -> None:
        for preset_name, preset_data in presets.items():
            name = hasattr(preset_name, "value") and preset_name.value or str(preset_name)
            preset_id = f"preset_{name}"
            existing = await self.get_by_name(name)
            if existing is None:
                profile = preset_data.model_copy(update={"id": preset_id, "name": name})
                await self.create(PersonaModel.from_profile(profile, is_preset=True))