"""
Persona / agent repository — compatibility layer over ``persola.db.models``.

Historically this module used a parallel ORM in ``tables.py`` (string PKs).
The active schema + Alembic stack is UUID-based ``PersonaModel`` / ``AgentModel``.
This file keeps the old ``PersonaRepo`` / ``AgentRepo`` API for callers while
reading and writing the canonical models.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AgentConfig, PersonaProfile
from .models import AgentModel, PersonaModel
from .repositories.agent_repository import AgentRepository
from .repositories.persona_repository import PersonaRepository


def _parse_uuid(value: str | UUID | None) -> UUID | None:
    if value is None or value == "":
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


class PersonaRepo:
    """Async repository wrapping persona DB operations (profile-shaped API)."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self._repo = PersonaRepository(session)

    async def create(self, profile: PersonaProfile) -> PersonaProfile:
        row = await self._repo.create(PersonaModel.from_profile(profile))
        await self.session.flush()
        return row.to_profile()

    async def get(self, persona_id: str) -> PersonaProfile | None:
        uid = _parse_uuid(persona_id)
        if uid is None:
            # Legacy string ids / preset names — try by name
            row = await self._repo.get_by_name(persona_id)
            return row.to_profile() if row else None
        row = await self._repo.get(uid)
        return row.to_profile() if row else None

    async def list_all(self) -> list[PersonaProfile]:
        rows = await self._repo.list(limit=500)
        return [r.to_profile() for r in rows]

    async def update(self, persona_id: str, profile: PersonaProfile) -> PersonaProfile | None:
        uid = _parse_uuid(persona_id)
        if uid is None:
            return None
        row = await self._repo.get(uid)
        if row is None:
            return None
        row.apply_profile(profile)
        await self.session.flush()
        await self.session.refresh(row)
        return row.to_profile()

    async def delete(self, persona_id: str) -> bool:
        uid = _parse_uuid(persona_id)
        if uid is None:
            return False
        return await self._repo.delete(uid)

    async def exists(self, persona_id: str) -> bool:
        return (await self.get(persona_id)) is not None

    async def search(self, query: str) -> list[PersonaProfile]:
        rows = await self._repo.search(query)
        return [r.to_profile() for r in rows]

    async def clone(self, persona_id: str, new_name: str) -> PersonaProfile | None:
        uid = _parse_uuid(persona_id)
        if uid is None:
            return None
        try:
            row = await self._repo.clone(uid, new_name)
        except ValueError:
            return None
        return row.to_profile()

    async def seed_presets(self, presets: dict) -> int:
        before = await self._repo.count()
        await self._repo.seed_presets(presets)
        after = await self._repo.count()
        return max(0, after - before)


class AgentRepo:
    """Async repository for agent DB operations (config-shaped API)."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self._repo = AgentRepository(session)

    async def create(self, config: AgentConfig) -> AgentConfig:
        row = await self._repo.create(AgentModel.from_config(config))
        await self.session.flush()
        return row.to_config()

    async def get(self, agent_id: str) -> AgentConfig | None:
        uid = _parse_uuid(agent_id)
        if uid is None:
            return None
        row = await self._repo.get(uid)
        return row.to_config() if row else None

    async def list_all(self) -> list[AgentConfig]:
        rows = await self._repo.list_active()
        return [r.to_config() for r in rows]

    async def update(self, agent_id: str, config: AgentConfig) -> AgentConfig | None:
        uid = _parse_uuid(agent_id)
        if uid is None:
            return None
        row = await self._repo.get(uid)
        if row is None:
            return None
        row.name = config.name
        row.role = config.role
        row.model = config.model
        row.temperature = config.temperature
        row.max_tokens = config.max_tokens
        row.system_prompt = config.system_prompt
        row.persona_id = _parse_uuid(config.persona_id)
        row.tools = list(config.tools or [])
        row.memory_enabled = config.memory_enabled
        await self.session.flush()
        await self.session.refresh(row)
        return row.to_config()

    async def delete(self, agent_id: str) -> bool:
        uid = _parse_uuid(agent_id)
        if uid is None:
            return False
        return await self._repo.delete(uid)

    async def exists(self, agent_id: str) -> bool:
        return (await self.get(agent_id)) is not None
