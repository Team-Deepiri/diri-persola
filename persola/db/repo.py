"""
Persona repository — replaces the in-memory personas_db dict.

Converts between PersonaProfile (Pydantic, used by engine/API)
and PersonaRow (SQLAlchemy, stored in Postgres).
"""

from typing import Optional
from datetime import datetime, timezone
import uuid

from sqlalchemy import select, delete, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import PersonaProfile, AgentConfig
from .tables import PersonaRow, AgentRow


# ── Fields shared between PersonaProfile and PersonaRow ──────────────────────
_KNOB_FIELDS = [
    "creativity", "humor", "formality", "verbosity", "empathy", "confidence",
    "openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism",
    "reasoning_depth", "step_by_step", "creativity_in_reasoning", "synthetics",
    "abstraction", "patterns",
    "accuracy", "reliability", "caution", "consistency", "self_correction", "transparency",
]

_SHARED_FIELDS = _KNOB_FIELDS + [
    "id", "name", "description", "system_prompt", "model", "temperature", "max_tokens",
]


def _row_to_profile(row: PersonaRow) -> PersonaProfile:
    """Convert a DB row to a Pydantic PersonaProfile."""
    data = {field: getattr(row, field) for field in _SHARED_FIELDS}
    data["created_at"] = row.created_at
    data["updated_at"] = row.updated_at
    return PersonaProfile(**data)


def _profile_to_row(profile: PersonaProfile, existing: Optional[PersonaRow] = None) -> PersonaRow:
    """Convert a Pydantic PersonaProfile to a DB row (or update an existing one)."""
    row = existing or PersonaRow()
    for field in _SHARED_FIELDS:
        setattr(row, field, getattr(profile, field))
    row.updated_at = datetime.now(timezone.utc)
    return row


class PersonaRepo:
    """Async repository wrapping all persona DB operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, profile: PersonaProfile) -> PersonaProfile:
        row = _profile_to_row(profile)
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return _row_to_profile(row)

    async def get(self, persona_id: str) -> Optional[PersonaProfile]:
        row = await self.session.get(PersonaRow, persona_id)
        if row is None:
            return None
        return _row_to_profile(row)

    async def list_all(self) -> list[PersonaProfile]:
        result = await self.session.execute(
            select(PersonaRow).where(PersonaRow.is_active == True).order_by(PersonaRow.created_at)
        )
        return [_row_to_profile(row) for row in result.scalars().all()]

    async def update(self, persona_id: str, profile: PersonaProfile) -> Optional[PersonaProfile]:
        row = await self.session.get(PersonaRow, persona_id)
        if row is None:
            return None
        _profile_to_row(profile, existing=row)
        row.id = persona_id  # keep original ID
        await self.session.flush()
        await self.session.refresh(row)
        return _row_to_profile(row)

    async def delete(self, persona_id: str) -> bool:
        result = await self.session.execute(
            delete(PersonaRow).where(PersonaRow.id == persona_id)
        )
        return result.rowcount > 0

    async def exists(self, persona_id: str) -> bool:
        row = await self.session.get(PersonaRow, persona_id)
        return row is not None

    async def search(self, query: str) -> list[PersonaProfile]:
        """Search personas by name or description (case-insensitive ILIKE)."""
        term = query.strip()
        if not term:
            return []

        pattern = f"%{term}%"
        result = await self.session.execute(
            select(PersonaRow)
            .where(PersonaRow.is_active == True)
            .where(
                or_(
                    PersonaRow.name.ilike(pattern),
                    PersonaRow.description.ilike(pattern),
                )
            )
            .order_by(PersonaRow.created_at)
        )
        return [_row_to_profile(row) for row in result.scalars().all()]

    async def clone(self, persona_id: str, new_name: str) -> Optional[PersonaProfile]:
        """Duplicate an existing persona with a new ID and name."""
        existing_row = await self.session.get(PersonaRow, persona_id)
        if existing_row is None:
            return None

        cloned = _row_to_profile(existing_row).model_copy(deep=True)
        cloned.id = f"persona_{uuid.uuid4().hex[:8]}"
        cloned.name = new_name
        return await self.create(cloned)

    async def seed_presets(self, presets: dict) -> int:
        """Idempotently insert presets if they are missing."""
        seeded = 0

        for key, preset_profile in presets.items():
            preset_key = key.value if hasattr(key, "value") else str(key)
            preset_id = f"preset_{preset_key}"

            if await self.session.get(PersonaRow, preset_id) is not None:
                continue

            profile = preset_profile.model_copy(deep=True)
            profile.id = preset_id
            await self.create(profile)
            seeded += 1

        return seeded


# ── Agent helpers ────────────────────────────────────────────────────────────

_AGENT_FIELDS = [
    "agent_id", "name", "role", "model", "temperature", "max_tokens",
    "system_prompt", "persona_id", "memory_enabled", "session_id",
]


def _agent_row_to_config(row: AgentRow) -> AgentConfig:
    data = {field: getattr(row, field) for field in _AGENT_FIELDS}
    data["tools"] = row.tools or []
    return AgentConfig(**data)


def _agent_config_to_row(config: AgentConfig, existing: Optional[AgentRow] = None) -> AgentRow:
    row = existing or AgentRow()
    for field in _AGENT_FIELDS:
        setattr(row, field, getattr(config, field))
    row.tools = config.tools or []
    row.updated_at = datetime.now(timezone.utc)
    return row


class AgentRepo:
    """Async repository for agent DB operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, config: AgentConfig) -> AgentConfig:
        row = _agent_config_to_row(config)
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return _agent_row_to_config(row)

    async def get(self, agent_id: str) -> Optional[AgentConfig]:
        row = await self.session.get(AgentRow, agent_id)
        if row is None:
            return None
        return _agent_row_to_config(row)

    async def list_all(self) -> list[AgentConfig]:
        result = await self.session.execute(
            select(AgentRow).where(AgentRow.is_active == True).order_by(AgentRow.created_at)
        )
        return [_agent_row_to_config(row) for row in result.scalars().all()]

    async def update(self, agent_id: str, config: AgentConfig) -> Optional[AgentConfig]:
        row = await self.session.get(AgentRow, agent_id)
        if row is None:
            return None
        _agent_config_to_row(config, existing=row)
        row.agent_id = agent_id
        await self.session.flush()
        await self.session.refresh(row)
        return _agent_row_to_config(row)

    async def delete(self, agent_id: str) -> bool:
        result = await self.session.execute(
            delete(AgentRow).where(AgentRow.agent_id == agent_id)
        )
        return result.rowcount > 0

    async def exists(self, agent_id: str) -> bool:
        row = await self.session.get(AgentRow, agent_id)
        return row is not None