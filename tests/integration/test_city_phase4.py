"""Phase 4 — live event poll/SSE contract and incremental cursors."""

from __future__ import annotations

from uuid import UUID

import pytest

from persola.services.city_service import CityService

pytestmark = pytest.mark.anyio


class TestEventCursor:
    async def test_poll_after_returns_only_new_events(self, db_session):
        service = CityService(db_session)
        family = await service.seed_wedge_family(name="Live Family")
        fid = UUID(family["id"])
        all_events = await service.list_events(family_id=fid)
        assert len(all_events) >= 2
        mid = all_events[1]["id"]
        newer = await service.list_events_since(family_id=fid, after_id=UUID(mid))
        assert all(e["id"] != mid for e in newer)
        older_ids = {e["id"] for e in all_events[:2]}
        assert older_ids.isdisjoint({e["id"] for e in newer})


class TestEventsAPI:
    async def test_poll_endpoint(self, http_client):
        seed = await http_client.post("/api/v1/city/wedge/seed", json={"name": "Poll Family"})
        assert seed.status_code == 200, seed.text
        fid = seed.json()["id"]

        r = await http_client.get("/api/v1/city/events", params={"family_id": fid})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["count"] >= 1
        types = {e["event_type"] for e in body["events"]}
        assert "family.created" in types or "agent.spawned" in types

        first_id = body["events"][0]["id"]
        # Run wedge to create more events
        run = await http_client.post("/api/v1/city/wedge/run", json={"family_id": fid})
        assert run.status_code == 200, run.text

        r2 = await http_client.get(
            "/api/v1/city/events",
            params={"family_id": fid, "after": first_id},
        )
        assert r2.status_code == 200
        assert r2.json()["count"] >= 1
        assert all(e["id"] != first_id for e in r2.json()["events"])

    async def test_sse_stream_hello(self, http_client):
        seed = await http_client.post("/api/v1/city/wedge/seed", json={"name": "SSE Family"})
        assert seed.status_code == 200
        fid = seed.json()["id"]

        async with http_client.stream(
            "GET",
            "/api/v1/city/events/stream",
            params={"family_id": fid, "poll_seconds": "0.1", "max_cycles": "1"},
        ) as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers.get("content-type", "")
            buf = "".join([chunk async for chunk in resp.aiter_text()])
        assert "event: city" in buf
        assert "stream.hello" in buf
        assert "stream.done" in buf

    async def test_events_require_scope(self, http_client):
        r = await http_client.get("/api/v1/city/events")
        assert r.status_code == 400
