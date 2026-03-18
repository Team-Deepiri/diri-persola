from typing import List, Optional, Dict, Any
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .base import BaseRepository
from ..models import PersonaModel, PersonaPresetModel
from ..schemas import PersonaCreate, PersonaUpdate


class PersonaRepository(BaseRepository[PersonaModel]):
    """Repository for persona operations."""

    @property
    def model_class(self):
        return PersonaModel

    async def create_persona(self, persona_data: PersonaCreate) -> PersonaModel:
        """Create a new persona with validation."""
        return await self.create(**persona_data.model_dump())

    async def get_persona(self, persona_id: str) -> Optional[PersonaModel]:
        """Retrieve persona by ID."""
        return await self.get_by_id(persona_id)

    async def get_persona_by_name(self, name: str) -> Optional[PersonaModel]:
        """Find persona by name."""
        result = await self.session.execute(
            select(PersonaModel).where(PersonaModel.name == name)
        )
        return result.scalar_one_or_none()

    async def list_personas(
        self,
        skip: int = 0,
        limit: int = 50,
        order_by: str = "created_at",
        order_desc: bool = True
    ) -> List[PersonaModel]:
        """List all personas with pagination."""
        return await self.filter(
            order_by=order_by,
            order_desc=order_desc,
            skip=skip,
            limit=limit
        )

    async def update_persona(self, persona_id: str, update_data: PersonaUpdate) -> Optional[PersonaModel]:
        """Update persona with optimistic locking."""
        return await self.update(persona_id, **update_data.model_dump(exclude_unset=True))

    async def delete_persona(self, persona_id: str) -> bool:
        """Delete persona (hard delete)."""
        return await self.delete(persona_id)

    async def search_personas(self, query: str, skip: int = 0, limit: int = 50) -> List[PersonaModel]:
        """Full-text search personas by name and description."""
        return await self.search(
            search_fields=["name", "description"],
            query=query,
            skip=skip,
            limit=limit
        )

    async def clone_persona(self, persona_id: str, new_name: str) -> Optional[PersonaModel]:
        """Duplicate an existing persona."""
        original = await self.get_persona(persona_id)
        if not original:
            return None

        # Create clone data
        clone_data = {
            "name": new_name,
            "description": f"Clone of {original.name}",
            "creativity": original.creativity,
            "humor": original.humor,
            "formality": original.formality,
            "verbosity": original.verbosity,
            "empathy": original.empathy,
            "confidence": original.confidence,
            "openness": original.openness,
            "conscientiousness": original.conscientiousness,
            "extraversion": original.extraversion,
            "agreeableness": original.agreeableness,
            "neuroticism": original.neuroticism,
            "reasoning_depth": original.reasoning_depth,
            "step_by_step": original.step_by_step,
            "creativity_in_reasoning": original.creativity_in_reasoning,
            "synthetics": original.synthetics,
            "abstraction": original.abstraction,
            "patterns": original.patterns,
            "accuracy": original.accuracy,
            "reliability": original.reliability,
            "caution": original.caution,
            "consistency": original.consistency,
            "self_correction": original.self_correction,
            "transparency": original.transparency,
            "system_prompt": original.system_prompt,
            "model": original.model,
            "temperature": original.temperature,
            "max_tokens": original.max_tokens,
        }

        return await self.create(**clone_data)

    async def get_persona_presets(self) -> List[PersonaPresetModel]:
        """Get all persona presets."""
        result = await self.session.execute(
            select(PersonaPresetModel).order_by(PersonaPresetModel.name)
        )
        return list(result.scalars().all())

    async def blend_personas(
        self,
        persona_id_1: str,
        persona_id_2: str,
        ratio: float = 0.5,
        name: str = None
    ) -> Optional[PersonaModel]:
        """Create blended persona from two sources."""
        persona1 = await self.get_persona(persona_id_1)
        persona2 = await self.get_persona(persona_id_2)

        if not persona1 or not persona2:
            return None

        if name is None:
            name = f"Blend of {persona1.name} and {persona2.name}"

        # Blend numeric parameters
        blend_data = {
            "name": name,
            "description": f"Blended persona ({ratio:.1f} {persona1.name} + {(1-ratio):.1f} {persona2.name})",
            "creativity": persona1.creativity * ratio + persona2.creativity * (1 - ratio),
            "humor": persona1.humor * ratio + persona2.humor * (1 - ratio),
            "formality": persona1.formality * ratio + persona2.formality * (1 - ratio),
            "verbosity": persona1.verbosity * ratio + persona2.verbosity * (1 - ratio),
            "empathy": persona1.empathy * ratio + persona2.empathy * (1 - ratio),
            "confidence": persona1.confidence * ratio + persona2.confidence * (1 - ratio),
            "openness": persona1.openness * ratio + persona2.openness * (1 - ratio),
            "conscientiousness": persona1.conscientiousness * ratio + persona2.conscientiousness * (1 - ratio),
            "extraversion": persona1.extraversion * ratio + persona2.extraversion * (1 - ratio),
            "agreeableness": persona1.agreeableness * ratio + persona2.agreeableness * (1 - ratio),
            "neuroticism": persona1.neuroticism * ratio + persona2.neuroticism * (1 - ratio),
            "reasoning_depth": persona1.reasoning_depth * ratio + persona2.reasoning_depth * (1 - ratio),
            "step_by_step": persona1.step_by_step * ratio + persona2.step_by_step * (1 - ratio),
            "creativity_in_reasoning": persona1.creativity_in_reasoning * ratio + persona2.creativity_in_reasoning * (1 - ratio),
            "synthetics": persona1.synthetics * ratio + persona2.synthetics * (1 - ratio),
            "abstraction": persona1.abstraction * ratio + persona2.abstraction * (1 - ratio),
            "patterns": persona1.patterns * ratio + persona2.patterns * (1 - ratio),
            "accuracy": persona1.accuracy * ratio + persona2.accuracy * (1 - ratio),
            "reliability": persona1.reliability * ratio + persona2.reliability * (1 - ratio),
            "caution": persona1.caution * ratio + persona2.caution * (1 - ratio),
            "consistency": persona1.consistency * ratio + persona2.consistency * (1 - ratio),
            "self_correction": persona1.self_correction * ratio + persona2.self_correction * (1 - ratio),
            "transparency": persona1.transparency * ratio + persona2.transparency * (1 - ratio),
            "temperature": persona1.temperature * ratio + persona2.temperature * (1 - ratio),
            "max_tokens": int(persona1.max_tokens * ratio + persona2.max_tokens * (1 - ratio)),
            "model": persona1.model,  # Use first persona's model
            "system_prompt": f"{persona1.system_prompt}\n\n{persona2.system_prompt}" if persona1.system_prompt and persona2.system_prompt else (persona1.system_prompt or persona2.system_prompt),
        }

        return await self.create(**blend_data)

    async def get_persona_stats(self) -> Dict[str, Any]:
        """Get statistics about personas."""
        result = await self.session.execute(
            select(
                func.count(PersonaModel.id).label("total_personas"),
                func.avg(PersonaModel.creativity).label("avg_creativity"),
                func.avg(PersonaModel.confidence).label("avg_confidence"),
                func.min(PersonaModel.created_at).label("oldest_persona"),
                func.max(PersonaModel.created_at).label("newest_persona"),
            )
        )
        row = result.first()
        return {
            "total_personas": row.total_personas,
            "avg_creativity": float(row.avg_creativity) if row.avg_creativity else 0.0,
            "avg_confidence": float(row.avg_confidence) if row.avg_confidence else 0.0,
            "oldest_persona": row.oldest_persona,
            "newest_persona": row.newest_persona,
        }