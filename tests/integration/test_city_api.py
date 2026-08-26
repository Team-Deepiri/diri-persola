"""Phase 1 communal city — families, jobs, commons, events."""

from __future__ import annotations

from uuid import UUID

import pytest

from persola.db.models import WorkspaceRunStatus
from persola.services.city_service import CityService, tool_names_for_tags

pytestmark = pytest.mark.anyio


async def _create_family(client, name: str = "Builder Clan") -> dict:
    r = await client.post(
        "/api/v1/city/families",
        json={"name": name, "description": "Phase 1 test family", "default_district": "build"},
    )
    assert r.status_code == 200, r.text
    return r.json()


class TestToolTagMapping:
    def test_workspace_and_run_tags(self):
        names = tool_names_for_tags(["workspace", "run"])
        assert "workspace_write" in names
        assert "run_python" in names


class TestCityFamilyAPI:
    async def test_create_family_has_parent_and_lineage(self, http_client):
        body = await _create_family(http_client)
        assert body["name"] == "Builder Clan"
        assert len(body["members"]) == 1
        assert body["members"][0]["role_in_family"] == "parent"
        assert body["lineage"]["edges"] == []
        assert body["members"][0]["agent"]["name"]

    async def test_list_families_includes_created(self, http_client):
        created = await _create_family(http_client, name="Listed Family")
        r = await http_client.get("/api/v1/city/families")
        assert r.status_code == 200
        ids = [f["id"] for f in r.json()]
        assert created["id"] in ids

    async def test_get_family_404(self, http_client):
        r = await http_client.get(f"/api/v1/city/families/{UUID(int=0)}")
        assert r.status_code == 404

    async def test_spawn_child_inherits_and_links_parent(self, http_client):
        family = await _create_family(http_client)
        r = await http_client.post(
            f"/api/v1/city/families/{family['id']}/spawn",
            json={
                "name": "Viz Child",
                "role_label": "creative",
                "knob_overrides": {"creativity": 0.95, "humor": 0.8},
            },
        )
        assert r.status_code == 200, r.text
        child = r.json()
        assert child["role_in_family"] == "child"
        assert child["parent_member_id"] == family["members"][0]["id"]
        assert child["knob_overrides"]["creativity"] == 0.95
        assert "workspace_write" in child["agent"]["tools"]

        detail = await http_client.get(f"/api/v1/city/families/{family['id']}")
        assert detail.status_code == 200
        graph = detail.json()
        assert len(graph["members"]) == 2
        assert len(graph["lineage"]["edges"]) == 1
        assert graph["lineage"]["edges"][0]["from"] == family["members"][0]["id"]

    async def test_family_events_include_spawn(self, http_client):
        family = await _create_family(http_client, name="Event Family")
        await http_client.post(
            f"/api/v1/city/families/{family['id']}/spawn",
            json={"name": "Runner", "role_label": "executor"},
        )
        r = await http_client.get(f"/api/v1/city/families/{family['id']}/events")
        assert r.status_code == 200
        types = [e["event_type"] for e in r.json()]
        assert "family.created" in types
        assert types.count("agent.spawned") >= 2


class TestCityJobAPI:
    async def test_start_job_pending_and_list_empty_commons(self, http_client):
        family = await _create_family(http_client, name="Job Family")
        r = await http_client.post(
            "/api/v1/city/jobs",
            json={
                "family_id": family["id"],
                "goal": "Build a hello script and run it",
                "district": "build",
            },
        )
        assert r.status_code == 200, r.text
        job = r.json()
        assert job["status"] == "pending"
        assert job["family_id"] == family["id"]

        got = await http_client.get(f"/api/v1/city/jobs/{job['id']}")
        assert got.status_code == 200
        assert got.json()["goal"].startswith("Build a hello")

        arts = await http_client.get(f"/api/v1/city/jobs/{job['id']}/artifacts")
        runs = await http_client.get(f"/api/v1/city/jobs/{job['id']}/runs")
        events = await http_client.get(f"/api/v1/city/jobs/{job['id']}/events")
        assert arts.status_code == 200 and arts.json() == []
        assert runs.status_code == 200 and runs.json() == []
        assert events.status_code == 200
        assert any(e["event_type"] == "job.started" for e in events.json())

    async def test_start_job_unknown_family_404(self, http_client):
        r = await http_client.post(
            "/api/v1/city/jobs",
            json={"family_id": str(UUID(int=1)), "goal": "noop"},
        )
        assert r.status_code == 404


class TestCityServiceCommons:
    async def test_record_artifact_and_run(self, db_session):
        service = CityService(db_session)
        family = await service.create_family(name="Commons Family", parent_name="Parent")
        family_id = UUID(family["id"])
        job = await service.start_job(family_id=family_id, goal="write and run")
        parent_agent_id = UUID(family["members"][0]["agent_id"])
        job_id = UUID(job["id"])

        artifact = await service.record_artifact(
            job_id=job_id,
            path="hello.py",
            content="print('hi')\n",
            created_by_agent_id=parent_agent_id,
        )
        assert artifact["path"] == "hello.py"
        assert artifact["version"] == 1

        run = await service.record_run(
            job_id=job_id,
            tool="run_python",
            args={"path": "hello.py"},
            status=WorkspaceRunStatus.SUCCEEDED.value,
            stdout="hi\n",
            duration_ms=12,
            started_by_agent_id=parent_agent_id,
            artifact_refs=[artifact["id"]],
        )
        assert run["status"] == "succeeded"

        arts = await service.list_artifacts(job_id)
        runs = await service.list_runs(job_id)
        assert len(arts) == 1
        assert len(runs) == 1

        detail = await service.get_job(job_id)
        assert detail is not None
        assert detail["artifact_count"] == 1
        assert detail["run_count"] == 1
