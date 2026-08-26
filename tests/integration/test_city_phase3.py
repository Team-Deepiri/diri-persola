"""Phase 3 — wedge family seed + multi-agent build/run demo."""

from __future__ import annotations

import pytest

from persola.services.city_service import CityService

pytestmark = pytest.mark.anyio


class TestWedgeDemo:
    async def test_seed_family_has_six_members(self, db_session):
        service = CityService(db_session)
        family = await service.seed_wedge_family(name="Unit Wedge Family")
        assert len(family["members"]) == 6  # parent + 5 children
        roles = {m.get("role_label") for m in family["members"]}
        assert {"coordinator", "analyst", "creative", "executor", "empath", "builder"} <= roles
        assert len(family["lineage"]["edges"]) == 5

    async def test_run_wedge_writes_and_runs(self, db_session):
        service = CityService(db_session)
        result = await service.run_wedge_demo(family_name="Run Wedge Family")
        assert result["success"] is True
        assert result["job"]["status"] == "completed"
        paths = {a["path"] for a in result["artifacts"]}
        assert "hello.py" in paths
        assert "notes/analysis.md" in paths
        assert any(r["tool"] == "run_python" and r["status"] == "succeeded" for r in result["runs"])
        # Multiple agents contributed artifacts
        authors = {
            a.get("created_by_agent_id")
            for a in result["artifacts"]
            if a.get("created_by_agent_id")
        }
        assert len(authors) >= 3
        event_types = {e["event_type"] for e in result["events"]}
        assert "cohesion.merge" in event_types
        assert "job.completed" in event_types


class TestWedgeAPI:
    async def test_wedge_run_endpoint(self, http_client):
        r = await http_client.post(
            "/api/v1/city/wedge/run",
            json={"family_name": "API Wedge", "goal": "Ship hello and show authorship"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["success"] is True
        assert body["job"]["status"] == "completed"
        assert any(a["path"] == "hello.py" for a in body["artifacts"])
        assert any(r0["status"] == "succeeded" for r0 in body["runs"])

        # Persist: fetch job views again
        job_id = body["job"]["id"]
        arts = await http_client.get(f"/api/v1/city/jobs/{job_id}/artifacts")
        runs = await http_client.get(f"/api/v1/city/jobs/{job_id}/runs")
        assert arts.status_code == 200 and len(arts.json()) >= 4
        assert runs.status_code == 200 and any(x["status"] == "succeeded" for x in runs.json())

    async def test_wedge_seed_then_run_on_family(self, http_client):
        seed = await http_client.post("/api/v1/city/wedge/seed", json={"name": "Seeded Wedge"})
        assert seed.status_code == 200, seed.text
        family = seed.json()
        assert len(family["members"]) == 6

        run = await http_client.post(
            "/api/v1/city/wedge/run",
            json={"family_id": family["id"]},
        )
        assert run.status_code == 200, run.text
        assert run.json()["family"]["id"] == family["id"]
        assert run.json()["success"] is True
