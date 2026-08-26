"""Phase 7 — city pulse, personality routing, cohesion merge/veto."""

from __future__ import annotations

from uuid import UUID

import pytest

from persola.orchestration.city_pulse import (
    DISTRICT_ROLE_PREFERENCE,
    district_tool_calls,
    pick_agent_for_district,
)
from persola.services.city_service import CityService

pytestmark = pytest.mark.anyio


class TestCityPulseRouting:
    def test_district_templates(self):
        build = district_tool_calls("build", family_slug="Alpha")
        assert build[0]["name"] == "workspace_write"
        assert any(c["name"] == "run_python" for c in build)

        viz = district_tool_calls("viz", family_slug="Beta")
        assert any(c["name"] == "emit_viz_event" for c in viz)

    def test_pick_agent_prefers_role(self):
        members = [
            {"role_label": "coordinator", "role_in_family": "parent", "agent_id": "p"},
            {"role_label": "creative", "role_in_family": "child", "agent_id": "c"},
            {"role_label": "executor", "role_in_family": "child", "agent_id": "e"},
        ]
        assert pick_agent_for_district(members, "viz")["agent_id"] == "c"
        assert pick_agent_for_district(members, "build")["agent_id"] == "e"
        assert "executor" in DISTRICT_ROLE_PREFERENCE["ops"]


class TestCityPulseService:
    async def test_pulse_and_cohesion_merge(self, db_session):
        service = CityService(db_session)
        # Small multi-district city
        await service.scale_probe(families=4, agents_per_family=4, name_prefix="P7", run_jobs=False)
        result = await service.city_pulse(max_families=4, auto_merge=True, name_prefix="p7")
        assert result["pulsed"] == 4
        assert result["merged"] + result["vetoed"] == 4
        assert result["avg_cohesion"] >= 0.0
        assert set(result["districts"].keys()) <= {"build", "viz", "research", "ops"}

        # Manual decide on a fresh job
        family = await service.create_family(name="DecideFam", parent_name="Boss")
        await service.spawn_child(UUID(family["id"]), name="Kid", role_label="executor")
        job = await service.start_job(family_id=UUID(family["id"]), goal="decide", district="build")
        agent_id = UUID(family["members"][0]["agent_id"])
        await service.execute_tool_calls(
            UUID(job["id"]),
            [
                {"name": "workspace_write", "args": {"path": "x.py", "content": "print(1)\n"}},
                {"name": "run_python", "args": {"path": "x.py"}},
            ],
            agent_id=agent_id,
        )
        merged = await service.cohesion_decide(UUID(job["id"]), action="merge", force=True)
        assert merged["decision"] == "merge"
        assert merged["job"]["status"] == "completed"

    async def test_cohesion_veto(self, db_session):
        service = CityService(db_session)
        family = await service.create_family(name="VetoFam", parent_name="Boss")
        job = await service.start_job(
            family_id=UUID(family["id"]), goal="veto-me", district="build"
        )
        vetoed = await service.cohesion_decide(UUID(job["id"]), action="veto", reason="not ready")
        assert vetoed["decision"] == "veto"
        assert vetoed["job"]["status"] == "failed"
        events = await service.list_events(job_id=UUID(job["id"]))
        assert any(e["event_type"] == "cohesion.veto" for e in events)


class TestCityPulseAPI:
    async def test_pulse_endpoint(self, http_client):
        seed = await http_client.post("/api/v1/city/wedge/seed", json={"name": "PulseSeed"})
        assert seed.status_code == 200
        pulse = await http_client.post(
            "/api/v1/city/pulse", json={"max_families": 2, "auto_merge": True}
        )
        assert pulse.status_code == 200
        body = pulse.json()
        assert body["pulsed"] >= 1
        assert "avg_cohesion" in body
