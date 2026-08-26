"""Phase 11 — memorial roll + Cyrex living sync (dry-run)."""

from __future__ import annotations

from uuid import UUID

import pytest

from persola.services.city_service import CityService

pytestmark = pytest.mark.anyio


class TestMemorial:
    async def test_memorial_lists_deceased_with_heirs(self, db_session):
        service = CityService(db_session)
        family = await service.create_family(
            name="MemFam",
            parent_name="Elder",
            policy={"max_age_ticks": 1},
        )
        await service.life_tick(force_age=1)
        mem = await service.city_memorial()
        assert mem["count"] >= 1
        assert mem["city"]["deceased"] >= 1
        entry = mem["memorial"][0]
        assert entry["heirs"]
        assert entry["generation"] >= 0


class TestCyrexDryRun:
    async def test_family_cyrex_dry_run_unconfigured(self, db_session, monkeypatch):
        monkeypatch.delenv("CYREX_URL", raising=False)
        monkeypatch.delenv("CYREX_API_KEY", raising=False)
        service = CityService(db_session)
        family = await service.create_family(name="CyrexFam", parent_name="Lead")
        result = await service.bulk_cyrex_sync(UUID(family["id"]), dry_run=True)
        assert result["configured"] is False
        assert result["synced"] == 0

    async def test_city_cyrex_dry_run_api(self, http_client):
        seed = await http_client.post("/api/v1/city/families", json={"name": "CyrexApi"})
        assert seed.status_code == 200
        resp = await http_client.post(
            "/api/v1/city/cyrex/sync", json={"dry_run": True, "max_families": 5}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "synced" in body
        assert body["dry_run"] is True

    async def test_memorial_endpoint(self, http_client):
        await http_client.post(
            "/api/v1/city/families",
            json={"name": "MemApi", "policy": {"max_age_ticks": 1}},
        )
        await http_client.post("/api/v1/city/life/tick", json={"force_age": 1})
        resp = await http_client.get("/api/v1/city/memorial")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] >= 1
        assert "memorial" in body
