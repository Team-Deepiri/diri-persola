from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
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
        query = select(PersonaModel).where(PersonaModel.name.ilike(f"%{query_text}%"))
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def clone(self, item_id: UUID, new_name: str) -> PersonaModel:
        original = await self.get(item_id)
        if original is None:
            raise ValueError("Persona not found")

        clone = PersonaModel(
            name=new_name,
            description=original.description,
            creativity=original.creativity,
            humor=original.humor,
            formality=original.formality,
            verbosity=original.verbosity,
            empathy=original.empathy,
            confidence=original.confidence,
            openness=original.openness,
            conscientiousness=original.conscientiousness,
            extraversion=original.extraversion,
            agreeableness=original.agreeableness,
            neuroticism=original.neuroticism,
            reasoning_depth=original.reasoning_depth,
            step_by_step=original.step_by_step,
            creativity_in_reasoning=original.creativity_in_reasoning,
            synthetics=original.synthetics,
            abstraction=original.abstraction,
            patterns=original.patterns,
            accuracy=original.accuracy,
            reliability=original.reliability,
            caution=original.caution,
            consistency=original.consistency,
            self_correction=original.self_correction,
            transparency=original.transparency,
            model=original.model,
            temperature=original.temperature,
            max_tokens=original.max_tokens,
            is_preset=False,
        )
        return await self.create(clone)

    async def seed_presets(self, presets: dict) -> None:
        for preset_name, preset_data in presets.items():
            name = hasattr(preset_name, "value") and preset_name.value or str(preset_name)
            existing = await self.get_by_name(name)
            if existing is None:
                payload = hasattr(preset_data, "model_dump") and preset_data.model_dump() or dict(preset_data)
                payload["name"] = name
                payload["is_preset"] = True
                await self.create(PersonaModel(**payload))