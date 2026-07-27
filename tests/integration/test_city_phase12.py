"""Phase 12 — chronicle timeline, city health, city-wide SSE filters."""

from __future__ import annotations

import pytest

from persola.services.city_service import CityService

pytestmark = pytest.mark.anyio


class TestChronicle:
	async def test_chronicle_life_only(self, db_session):
		service = CityService(db_session)
		await service.create_family(name="ChronFam", parent_name="Elder", policy={"max_age_ticks": 1})
		await service.life_tick(force_age=1)
		ch = await service.city_chronicle(life_only=True, limit=50)
		assert ch["chronicle_version"] == "1.0"
		assert ch["count"] >= 1
		types = {e["event_type"] for e in ch["events"]}
		assert "member.died" in types or "legacy.passed" in types or "life.aged" in types
		assert ch["memorial_count"] >= 1

	async def test_city_health(self, db_session):
		service = CityService(db_session)
		health = await service.city_health()
		assert health["ok"] is True
		assert health["db"] is True
		assert "status" in health


class TestChronicleAPI:
	async def test_endpoints(self, http_client):
		await http_client.post(
			"/api/v1/city/families",
			json={"name": "ChronApi", "policy": {"max_age_ticks": 1}},
		)
		await http_client.post("/api/v1/city/life/tick", json={"force_age": 1})

		ch = await http_client.get("/api/v1/city/chronicle", params={"life_only": True})
		assert ch.status_code == 200
		assert ch.json()["count"] >= 1

		health = await http_client.get("/api/v1/city/health")
		assert health.status_code == 200
		assert health.json()["ok"] is True

	async def test_city_wide_sse_hello(self, http_client):
		resp = await http_client.get(
			"/api/v1/city/events/stream",
			params={
				"city_wide": True,
				"types": "member.died,legacy.passed",
				"max_cycles": 1,
				"poll_seconds": 0.25,
			},
		)
		assert resp.status_code == 200
		body = resp.text
		assert "stream.hello" in body
		assert "city_wide" in body
