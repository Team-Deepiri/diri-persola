"""Phase 5 — scale governor, workers, probe ≥50 agents / ≥5 families."""

from __future__ import annotations

import asyncio
from uuid import UUID

import pytest

from persola.orchestration.city_scale import ConcurrencyGovernor, ModelTier, ScaleConfig, shard_for_district
from persola.orchestration.city_worker import CITY_WORKER_POOL
from persola.services.city_service import CityService

pytestmark = pytest.mark.anyio


class TestScalePrimitives:
	def test_model_tiers(self):
		tiers = ModelTier(parent="big", child="small")
		assert tiers.for_role("parent", "coordinator") == "big"
		assert tiers.for_role("child", "executor") == "small"

	def test_district_shard(self):
		assert shard_for_district("viz") == "district:viz"
		assert shard_for_district("unknown") == "district:build"

	async def test_governor_limits_per_family(self):
		gov = ConcurrencyGovernor(ScaleConfig(max_global_concurrent=4, max_per_family=1, max_per_district=4))
		await gov.acquire(family_id="f1", district="build")

		async def second():
			await gov.acquire(family_id="f1", district="build")
			gov.release(family_id="f1", district="build")

		task = asyncio.create_task(second())
		await asyncio.sleep(0.05)
		assert not task.done()
		gov.release(family_id="f1", district="build")
		await asyncio.wait_for(task, timeout=1.0)


class TestScaleProbe:
	async def test_probe_meets_fifty_agents_five_families(self, db_session):
		service = CityService(db_session)
		result = await service.scale_probe(
			families=5,
			agents_per_family=10,
			name_prefix="P5",
			run_jobs=True,
		)
		assert result["families"] == 5
		assert result["agents"] == 50
		assert result["meets_probe_bar"] is True
		assert result["jobs"] == 5
		# Model tiers applied: parent strong, child cheap defaults
		family = await service.get_family(UUID(result["family_ids"][0]))
		assert family is not None
		parent = next(m for m in family["members"] if m["role_in_family"] == "parent")
		child = next(m for m in family["members"] if m["role_in_family"] == "child")
		# Agents store model on agent row — reload via list is enough through serialize
		parent_agent = await service.agents.get(UUID(parent["agent_id"]))
		child_agent = await service.agents.get(UUID(child["agent_id"]))
		assert parent_agent is not None and child_agent is not None
		assert parent_agent.model == service.model_tiers.parent
		assert child_agent.model == service.model_tiers.child

	async def test_cohesion_score(self, db_session):
		service = CityService(db_session)
		probe = await service.scale_probe(families=1, agents_per_family=3, name_prefix="Coh", run_jobs=True)
		job_id = UUID(probe["job_ids"][0])
		score = await service.cohesion_score(job_id)
		assert 0.0 <= score["score"] <= 1.0
		assert score["run_count"] >= 1


class TestWorkerPool:
	async def test_enqueue_and_complete(self, db_session):
		from contextlib import asynccontextmanager

		service = CityService(db_session)
		family = await service.create_family(name="WorkerFam", parent_name="P")
		job = await service.start_job(family_id=UUID(family["id"]), goal="enqueue")
		agent_id = UUID(family["members"][0]["agent_id"])

		@asynccontextmanager
		async def _factory():
			yield db_session

		CITY_WORKER_POOL.set_session_factory(_factory)
		try:
			if CITY_WORKER_POOL._started:
				await CITY_WORKER_POOL.stop()
			result = await service.enqueue_job_tools(
				UUID(job["id"]),
				[
					{"name": "workspace_write", "args": {"path": "w.py", "content": "print(1)\n"}},
					{"name": "run_python", "args": {"path": "w.py"}},
				],
				agent_id=agent_id,
				wait=True,
			)
			assert result["status"] == "completed"
			assert result["result"] is not None
			runs = await service.list_runs(UUID(job["id"]))
			assert any(r["tool"] == "run_python" and r["status"] == "succeeded" for r in runs)
		finally:
			await CITY_WORKER_POOL.stop()
			CITY_WORKER_POOL.set_session_factory(None)


class TestScaleAPI:
	async def test_scale_path_and_status(self, http_client):
		path = await http_client.get("/api/v1/city/scale/path")
		assert path.status_code == 200
		body = path.json()
		assert body["target_agents"] == 100
		assert len(body["bottlenecks"]) >= 3

		status = await http_client.get("/api/v1/city/scale/status")
		assert status.status_code == 200
		assert "governor" in status.json()

	async def test_scale_probe_api(self, http_client):
		r = await http_client.post(
			"/api/v1/city/scale/probe",
			json={"families": 5, "agents_per_family": 10, "name_prefix": "API5", "run_jobs": False},
		)
		assert r.status_code == 200, r.text
		body = r.json()
		assert body["meets_probe_bar"] is True
		assert body["agents"] == 50

	async def test_cyrex_sync_unconfigured(self, http_client):
		seed = await http_client.post("/api/v1/city/wedge/seed", json={"name": "CyrexFam"})
		assert seed.status_code == 200
		fid = seed.json()["id"]
		r = await http_client.post(f"/api/v1/city/families/{fid}/cyrex/sync")
		assert r.status_code == 200
		assert r.json()["configured"] is False
