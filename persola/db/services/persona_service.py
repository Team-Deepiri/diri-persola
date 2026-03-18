from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories.persona_repository import PersonaRepository
from ..schemas import PersonaCreate, PersonaUpdate, PersonaResponse
from ..models import PersonaModel


class PersonaService:
    """Business logic for persona operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = PersonaRepository(session)

    async def create_persona(self, persona_data: PersonaCreate) -> PersonaModel:
        """Create a new persona with validation."""
        # Additional validation can be added here
        await self._validate_persona_data(persona_data)
        return await self.repository.create_persona(persona_data)

    async def get_persona(self, persona_id: str) -> Optional[PersonaModel]:
        """Retrieve persona by ID."""
        return await self.repository.get_persona(persona_id)

    async def update_persona(self, persona_id: str, update_data: PersonaUpdate) -> Optional[PersonaModel]:
        """Update persona with validation."""
        if update_data.model_dump(exclude_unset=True):
            await self._validate_update_data(update_data)
        return await self.repository.update_persona(persona_id, update_data)

    async def delete_persona(self, persona_id: str) -> bool:
        """Delete persona."""
        return await self.repository.delete_persona(persona_id)

    async def list_personas(
        self,
        skip: int = 0,
        limit: int = 50,
        order_by: str = "created_at",
        order_desc: bool = True
    ) -> List[PersonaModel]:
        """List personas with pagination."""
        return await self.repository.list_personas(skip, limit, order_by, order_desc)

    async def search_personas(self, query: str, skip: int = 0, limit: int = 50) -> List[PersonaModel]:
        """Search personas."""
        return await self.repository.search_personas(query, skip, limit)

    async def apply_preset(self, persona_id: str, preset_name: str) -> Optional[PersonaModel]:
        """Apply a preset configuration to a persona."""
        # This would load preset data and apply it
        # For now, return the persona unchanged
        return await self.get_persona(persona_id)

    async def validate_knobs(self, knobs: Dict[str, float]) -> Dict[str, Any]:
        """Validate tuning parameters."""
        errors = {}
        valid_ranges = {
            "creativity": (0.0, 1.0),
            "humor": (0.0, 1.0),
            "formality": (0.0, 1.0),
            "verbosity": (0.0, 1.0),
            "empathy": (0.0, 1.0),
            "confidence": (0.0, 1.0),
            "openness": (0.0, 1.0),
            "conscientiousness": (0.0, 1.0),
            "extraversion": (0.0, 1.0),
            "agreeableness": (0.0, 1.0),
            "neuroticism": (0.0, 1.0),
            "reasoning_depth": (0.0, 1.0),
            "step_by_step": (0.0, 1.0),
            "creativity_in_reasoning": (0.0, 1.0),
            "synthetics": (0.0, 1.0),
            "abstraction": (0.0, 1.0),
            "patterns": (0.0, 1.0),
            "accuracy": (0.0, 1.0),
            "reliability": (0.0, 1.0),
            "caution": (0.0, 1.0),
            "consistency": (0.0, 1.0),
            "self_correction": (0.0, 1.0),
            "transparency": (0.0, 1.0),
            "temperature": (0.0, 2.0),
        }

        for knob, value in knobs.items():
            if knob in valid_ranges:
                min_val, max_val = valid_ranges[knob]
                if not (min_val <= value <= max_val):
                    errors[knob] = f"Must be between {min_val} and {max_val}"
            else:
                errors[knob] = "Unknown knob parameter"

        return {"valid": len(errors) == 0, "errors": errors}

    async def export_persona(self, persona_id: str) -> Optional[Dict[str, Any]]:
        """Export persona to JSON."""
        persona = await self.get_persona(persona_id)
        if not persona:
            return None

        return {
            "id": persona.id,
            "name": persona.name,
            "description": persona.description,
            "created_at": persona.created_at.isoformat(),
            "updated_at": persona.updated_at.isoformat(),
            "knobs": persona.get_knobs(),
            "system_prompt": persona.system_prompt,
            "model": persona.model,
            "temperature": persona.temperature,
            "max_tokens": persona.max_tokens,
        }

    async def import_persona(self, persona_data: Dict[str, Any], name: Optional[str] = None) -> PersonaModel:
        """Import persona from JSON."""
        # Extract knob values
        knobs = persona_data.get("knobs", {})

        # Validate knobs
        validation = await self.validate_knobs(knobs)
        if not validation["valid"]:
            raise ValueError(f"Invalid knob values: {validation['errors']}")

        # Create persona data
        create_data = PersonaCreate(
            name=name or persona_data.get("name", "Imported Persona"),
            description=persona_data.get("description", ""),
            **knobs,
            system_prompt=persona_data.get("system_prompt"),
            model=persona_data.get("model", "llama3:8b"),
            temperature=persona_data.get("temperature", 0.7),
            max_tokens=persona_data.get("max_tokens", 2000),
        )

        return await self.create_persona(create_data)

    async def clone_persona(self, persona_id: str, new_name: str) -> Optional[PersonaModel]:
        """Clone an existing persona."""
        return await self.repository.clone_persona(persona_id, new_name)

    async def blend_personas(
        self,
        persona_id_1: str,
        persona_id_2: str,
        ratio: float = 0.5,
        name: Optional[str] = None
    ) -> Optional[PersonaModel]:
        """Blend two personas."""
        if not (0.0 <= ratio <= 1.0):
            raise ValueError("Ratio must be between 0.0 and 1.0")

        return await self.repository.blend_personas(persona_id_1, persona_id_2, ratio, name)

    async def get_persona_presets(self) -> List[Dict[str, Any]]:
        """Get available persona presets."""
        presets = await self.repository.get_persona_presets()
        return [
            {
                "id": preset.id,
                "name": preset.name,
                "description": preset.description,
                "is_default": preset.is_default,
            }
            for preset in presets
        ]

    async def get_persona_stats(self) -> Dict[str, Any]:
        """Get persona statistics."""
        return await self.repository.get_persona_stats()

    async def _validate_persona_data(self, data: PersonaCreate) -> None:
        """Validate persona creation data."""
        # Check name uniqueness
        existing = await self.repository.get_persona_by_name(data.name)
        if existing:
            raise ValueError(f"Persona with name '{data.name}' already exists")

    async def _validate_update_data(self, data: PersonaUpdate) -> None:
        """Validate persona update data."""
        # Check name uniqueness if name is being updated
        if data.name:
            existing = await self.repository.get_persona_by_name(data.name)
            if existing:
                raise ValueError(f"Persona with name '{data.name}' already exists")