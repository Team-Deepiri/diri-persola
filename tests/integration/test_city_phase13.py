"""Phase 13 — generation continuity proof + policy / life edits."""

from __future__ import annotations

from uuid import UUID

import pytest

from persola.services.city_service import CityService

pytestmark = pytest.mark.anyio


class TestGenerations:
    async def test_generation_report_after_death(self, db_session):
        service = CityService(db_session)
        family = await service.create_family(
            name="GenFam",
            parent_name="Founder",
            policy={"max_age_ticks": 1},
            role_label="coordinator",
        )
        await service.spawn_child(UUID(family["id"]), name="Kid", role_label="executor")
        await service.life_tick(force_age=1)
        report = await service.generation_report()
        assert report["generations"]
        assert report["legacy_edges"] >= 1
        assert report["last_life_proof"] is not None
        assert report["last_life_proof"]["efficiency_preserved"] is True
        assert "thesis" in report
        gens = {g["generation"] for g in report["generations"]}
        assert 0 in gens or 1 in gens

    async def test_policy_and_member_life(self, db_session):
        service = CityService(db_session)
        family = await service.create_family(name="PolicyFam", parent_name="Lead")
        fid = UUID(family["id"])
        updated = await service.update_family_policy(fid, {"max_age_ticks": 4, "cohesion_min": 0.4})
        assert updated["policy"]["max_age_ticks"] == 4
        member_id = UUID(updated["members"][0]["id"])
        life = await service.update_member_life(
            member_id,
            goals=["ship the commons", "teach the next era"],
            dreams=["a city that outlives us"],
            structured_thinking=0.8,
        )
        assert "ship the commons" in life["goals"]
        assert life["structured_thinking"] == pytest.approx(0.8)


class TestGenerationsAPI:
    async def test_endpoints(self, http_client):
        seed = await http_client.post(
            "/api/v1/city/families",
            json={"name": "GenApi", "policy": {"max_age_ticks": 1}},
        )
        assert seed.status_code == 200
        fid = seed.json()["id"]
        await http_client.post("/api/v1/city/life/tick", json={"force_age": 1})

        gens = await http_client.get("/api/v1/city/generations")
        assert gens.status_code == 200
        body = gens.json()
        assert "generations" in body
        assert body["last_life_proof"] is not None

        pol = await http_client.patch(
            f"/api/v1/city/families/{fid}/policy",
            json={"max_age_ticks": 5},
        )
        assert pol.status_code == 200
        assert pol.json()["policy"]["max_age_ticks"] == 5
