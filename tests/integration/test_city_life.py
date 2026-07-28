"""Phase 7/8 — ecosystem cohesion + generational death/succession."""

from __future__ import annotations

from uuid import UUID

import pytest

from persola.services.city_service import CityService

pytestmark = pytest.mark.anyio


class TestEcosystemAndLife:
	async def test_ecosystem_has_goals_and_cohesion(self, db_session):
		service = CityService(db_session)
		family = await service.create_family(
			name="EcoFam",
			parent_name="Lead",
			policy={"max_age_ticks": 20},
		)
		await service.spawn_child(UUID(family["id"]), name="Exec", role_label="executor")
		await service.spawn_child(UUID(family["id"]), name="Analyst", role_label="analyst")

		eco = await service.city_ecosystem()
		assert eco["city"]["living"] >= 3
		assert eco["city"]["deceased"] == 0
		block = next(e for e in eco["ecosystems"] if e["family_id"] == family["id"])
		assert block["cohesion"] > 0
		assert block["goals"]
		assert any(m.get("dreams") for m in block["members"])

	async def test_death_passes_legacy_preserves_efficiency(self, db_session):
		service = CityService(db_session)
		family = await service.create_family(
			name="MortalFam",
			parent_name="Elder",
			policy={"max_age_ticks": 2},
			role_label="coordinator",
		)
		fid = UUID(family["id"])
		await service.spawn_child(fid, name="Worker", role_label="executor")

		# Seed completed work so efficiency denominator matters
		job = await service.start_job(family_id=fid, goal="seed work", district="build")
		await service.set_job_status(UUID(job["id"]), status="completed", result_summary="done")

		tick1 = await service.life_tick(force_age=1)
		assert tick1["aged"] >= 2
		assert tick1["died"] == 0

		tick2 = await service.life_tick(force_age=1)
		assert tick2["died"] >= 1
		assert tick2["born"] >= 1
		assert tick2["efficiency_preserved"] is True

		detail = await service.get_family(fid)
		assert detail is not None
		deceased = [m for m in detail["members"] if m["life_status"] == "deceased"]
		living = [m for m in detail["members"] if m["life_status"] == "alive"]
		assert deceased
		assert living
		assert any(m.get("successor_of_id") for m in living)
		assert any(m.get("generation", 0) >= 1 for m in living)

		events = await service.list_events(family_id=fid, limit=80)
		types = {e["event_type"] for e in events}
		assert "member.died" in types
		assert "legacy.passed" in types


class TestLifeAPI:
	async def test_ecosystem_and_life_endpoints(self, http_client):
		seed = await http_client.post(
			"/api/v1/city/families",
			json={"name": "ApiLife", "parent_name": "P", "policy": {"max_age_ticks": 1}},
		)
		assert seed.status_code == 200

		eco = await http_client.get("/api/v1/city/ecosystem")
		assert eco.status_code == 200
		body = eco.json()
		assert "ecosystems" in body
		assert "city" in body

		life = await http_client.post("/api/v1/city/life/tick", json={"force_age": 1})
		assert life.status_code == 200
		payload = life.json()
		assert payload["died"] >= 1
		assert payload["born"] >= 1
		assert "efficiency_preserved" in payload
