"""Phase 10 — city conductor (LLM team-invoke or tool fallback)."""

from __future__ import annotations

from uuid import UUID

import pytest

from persola.services.city_service import CityService

pytestmark = pytest.mark.anyio


class TestCityConductor:
	async def test_conduct_tools_fallback(self, db_session):
		service = CityService(db_session)
		await service.scale_probe(families=3, agents_per_family=4, name_prefix="P10", run_jobs=False)
		result = await service.conduct_city(
			max_families=3,
			llm_fn=None,  # deterministic tool path
			auto_merge=True,
		)
		assert result["mode"] == "tools"
		assert result["conducted"] == 3
		assert result["merged"] + result["vetoed"] == 3
		assert any(r["ok"] for r in result["results"])

	async def test_conduct_with_stub_llm(self, db_session):
		service = CityService(db_session)
		family = await service.create_family(name="ConductLLM", parent_name="Lead")
		await service.spawn_child(UUID(family["id"]), name="Exec", role_label="executor")

		async def stub_llm(system: str, user: str) -> str:
			return (
				'COORDINATOR: plan write+run\n'
				'EXECUTOR: TOOL_CALL workspace_write {"path":"conduct/stub.py","content":"print(\\"city-conduct-ok\\")\\n"}\n'
				'EXECUTOR: TOOL_CALL run_python {"path":"conduct/stub.py"}\n'
			)

		result = await service.conduct_city(
			max_families=1,
			llm_fn=stub_llm,
			use_langgraph=False,
			auto_merge=True,
		)
		assert result["mode"] == "llm"
		assert result["conducted"] >= 1
		job_id = UUID(result["results"][0]["job_id"])
		events = await service.list_events(job_id=job_id)
		assert any(e["event_type"] == "city.conduct.started" for e in events)
		assert any(e["event_type"] == "city.conduct.finished" for e in events)


class TestConductAPI:
	async def test_conduct_endpoint_tools(self, http_client):
		seed = await http_client.post("/api/v1/city/wedge/seed", json={"name": "ConductSeed"})
		assert seed.status_code == 200
		resp = await http_client.post(
			"/api/v1/city/conduct",
			json={"max_families": 2, "use_llm": False, "auto_merge": True},
		)
		assert resp.status_code == 200
		body = resp.json()
		assert body["mode"] == "tools"
		assert body["conducted"] >= 1
