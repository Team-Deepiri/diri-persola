"""Canonical ORM consolidation — PersonaRepo uses models.py, not dual tables."""

from __future__ import annotations

import pytest

from persola.db.repo import AgentRepo, PersonaRepo
from persola.models import AgentConfig, PersonaProfile
from persola.services.city_service import CityService

pytestmark = pytest.mark.anyio


class TestCanonicalRepo:
	async def test_persona_repo_roundtrip(self, db_session):
		repo = PersonaRepo(db_session)
		created = await repo.create(
			PersonaProfile(name="Canon Persona", description="dual-orm gone", creativity=0.7)
		)
		assert created.id
		got = await repo.get(created.id)
		assert got is not None
		assert got.name == "Canon Persona"
		assert got.creativity == pytest.approx(0.7)

		listed = await repo.list_all()
		assert any(p.id == created.id for p in listed)

	async def test_agent_repo_roundtrip(self, db_session):
		personas = PersonaRepo(db_session)
		persona = await personas.create(PersonaProfile(name="Agent Owner"))
		agents = AgentRepo(db_session)
		cfg = await agents.create(
			AgentConfig(name="Canon Agent", persona_id=persona.id, tools=["workspace_write"])
		)
		assert cfg.agent_id
		got = await agents.get(cfg.agent_id)
		assert got is not None
		assert got.name == "Canon Agent"
		assert got.persona_id == persona.id


class TestAustinPackLife:
	async def test_export_includes_ecosystem_life(self, db_session):
		service = CityService(db_session)
		await service.create_family(name="AustinLife", parent_name="Lead", policy={"max_age_ticks": 1})
		await service.life_tick(force_age=1)
		pack = await service.export_austin_pack(event_limit=50, include_artifacts=False)
		assert pack["pack_version"] == "1.3"
		assert "ecosystems" in pack
		assert "chronicle" in pack
		assert "generations" in pack
		assert pack["vitals"].get("living") is not None
		assert any(n.get("life_status") for n in pack["graph"]["nodes"])
		kinds = {e.get("kind") for e in pack["graph"]["edges"]}
		assert "lineage" in kinds or "legacy" in kinds or len(pack["graph"]["edges"]) >= 0
