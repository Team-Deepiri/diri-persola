"""Phase 8 — multi-contributor pulse + city heartbeat."""

from __future__ import annotations

import pytest

from persola.orchestration.city_pulse import multi_contributor_plan
from persola.services.city_service import LAST_CITY_HEARTBEAT, CityService

pytestmark = pytest.mark.anyio


class TestMultiContributor:
	def test_plan_has_support_and_lead(self):
		members = [
			{"role_label": "coordinator", "role_in_family": "parent", "agent_id": "p"},
			{"role_label": "analyst", "role_in_family": "child", "agent_id": "a"},
			{"role_label": "creative", "role_in_family": "child", "agent_id": "c"},
			{"role_label": "executor", "role_in_family": "child", "agent_id": "e"},
			{"role_label": "empath", "role_in_family": "child", "agent_id": "m"},
		]
		plan = multi_contributor_plan(members, district="build", family_slug="Fam")
		roles = [b["role_label"] for b in plan]
		assert "analyst" in roles
		assert "creative" in roles
		assert "executor" in roles
		assert plan[-1]["role_label"] == "executor"
		assert len(plan[-1]["calls"]) >= 2


class TestHeartbeat:
	async def test_multi_contributor_pulse_and_heartbeat(self, db_session):
		LAST_CITY_HEARTBEAT.clear()
		service = CityService(db_session)
		await service.scale_probe(families=4, agents_per_family=5, name_prefix="P8", run_jobs=False)
		pulse = await service.city_pulse(max_families=4, multi_contributor=True, auto_merge=True)
		assert pulse["pulsed"] == 4
		assert pulse["avg_contributors"] >= 2
		assert pulse["multi_contributor"] is True
		assert any(r["contributor_count"] >= 2 for r in pulse["results"])

		hb = await service.city_heartbeat()
		assert hb["alive"] is True
		assert hb["last_pulse"]["pulsed"] == 4
		assert hb["suggested_tick"]["multi_contributor"] is True

	async def test_heartbeat_tick_api(self, http_client):
		seed = await http_client.post("/api/v1/city/wedge/seed", json={"name": "BeatSeed"})
		assert seed.status_code == 200
		tick = await http_client.post("/api/v1/city/heartbeat/tick")
		assert tick.status_code == 200
		body = tick.json()
		assert body["pulse"]["pulsed"] >= 1
		assert body["vitals"]["alive"] is True
		hb = await http_client.get("/api/v1/city/heartbeat")
		assert hb.status_code == 200
		assert hb.json()["last_pulse"]
