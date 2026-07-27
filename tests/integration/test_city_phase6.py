"""Phase 6 — prove ≥100 distinct personalities + city snapshot / awaken APIs."""

from __future__ import annotations

from uuid import UUID

import pytest

from persola.orchestration.city_personalities import (
	distinct_child_personality,
	parent_personality,
	personality_fingerprint,
)
from persola.services.city_service import CityService

pytestmark = pytest.mark.anyio


class TestCityPersonalities:
	def test_child_fingerprints_are_unique_across_hundred(self):
		fps = set()
		for fam in range(10):
			fps.add(parent_personality(family_index=fam)["fingerprint"])
			for child in range(9):
				fps.add(distinct_child_personality(child_index=child, family_index=fam)["fingerprint"])
		assert len(fps) == 100

	def test_fingerprint_stable(self):
		a = distinct_child_personality(child_index=3, family_index=2)
		b = distinct_child_personality(child_index=3, family_index=2)
		assert a["fingerprint"] == b["fingerprint"]
		assert a["fingerprint"] == personality_fingerprint(a["knob_overrides"])


class TestHundredAwaken:
	async def test_hundred_probe_unique_personalities(self, db_session):
		service = CityService(db_session)
		result = await service.scale_probe(
			mode="hundred",
			name_prefix="P6",
			run_jobs=True,
		)
		assert result["agents"] == 100
		assert result["families"] == 10
		assert result["meets_hundred_bar"] is True
		assert result["meets_probe_bar"] is True
		assert result["all_personalities_unique"] is True
		assert result["distinct_personalities"] == 100
		assert sum(result["districts"].values()) == 10

		# Spot-check member serialization includes personality fingerprint
		family = await service.get_family(UUID(result["family_ids"][0]))
		assert family is not None
		assert all((m.get("personality") or {}).get("fingerprint") for m in family["members"])

	async def test_city_snapshot(self, db_session):
		service = CityService(db_session)
		await service.scale_probe(families=2, agents_per_family=3, name_prefix="Snap", run_jobs=False)
		snap = await service.city_snapshot()
		assert snap["family_count"] >= 2
		assert snap["agent_count"] >= 6
		assert snap["distinct_personalities"] >= 1
		assert "build" in snap["districts"]
		assert snap["progress"] >= 0.0


class TestPhase6API:
	async def test_awaken_and_snapshot_endpoints(self, http_client):
		awaken = await http_client.post("/api/v1/city/scale/awaken")
		assert awaken.status_code == 200
		body = awaken.json()
		assert body["meets_hundred_bar"] is True
		assert body["agents"] == 100
		assert body["all_personalities_unique"] is True

		snap = await http_client.get("/api/v1/city/snapshot")
		assert snap.status_code == 200
		s = snap.json()
		assert s["agent_count"] >= 100
		assert s["family_count"] >= 10
		assert len(s["families"]) >= 10

		path = await http_client.get("/api/v1/city/scale/path")
		assert path.status_code == 200
		assert path.json()["hundred_default"]["total"] == 100
