"""Integration tests – Persona CRUD via test HTTP client + SQLite DB."""

import pytest


pytestmark = pytest.mark.anyio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_persona(client, payload: dict) -> dict:
    r = await client.post("/api/v1/personas", json=payload)
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

class TestCreatePersona:
    async def test_create_returns_200(self, http_client, persona_payload):
        r = await http_client.post("/api/v1/personas", json=persona_payload)
        assert r.status_code == 200

    async def test_create_response_contains_name(self, http_client, persona_payload):
        body = await _create_persona(http_client, persona_payload)
        assert body["name"] == persona_payload["name"]

    async def test_create_response_contains_id(self, http_client, persona_payload):
        body = await _create_persona(http_client, persona_payload)
        assert "id" in body and body["id"]

    async def test_create_returns_knob_values(self, http_client, persona_payload):
        body = await _create_persona(http_client, persona_payload)
        assert abs(body["creativity"] - persona_payload["creativity"]) < 0.001

    async def test_name_too_long_returns_422(self, http_client):
        r = await http_client.post("/api/v1/personas", json={"name": "x" * 201})
        assert r.status_code == 422

    async def test_knob_over_one_returns_422(self, http_client):
        r = await http_client.post("/api/v1/personas", json={"name": "P", "creativity": 1.1})
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

class TestGetPersona:
    async def test_get_existing_returns_200(self, http_client, persona_payload):
        created = await _create_persona(http_client, persona_payload)
        r = await http_client.get(f"/api/v1/personas/{created['id']}")
        assert r.status_code == 200

    async def test_get_existing_returns_correct_name(self, http_client, persona_payload):
        created = await _create_persona(http_client, persona_payload)
        r = await http_client.get(f"/api/v1/personas/{created['id']}")
        assert r.json()["name"] == persona_payload["name"]

    async def test_get_nonexistent_returns_404(self, http_client):
        import uuid
        r = await http_client.get(f"/api/v1/personas/{uuid.uuid4()}")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

class TestListPersonas:
    async def test_empty_list_returns_200(self, http_client):
        r = await http_client.get("/api/v1/personas")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    async def test_created_persona_appears_in_list(self, http_client, persona_payload):
        await _create_persona(http_client, persona_payload)
        r = await http_client.get("/api/v1/personas")
        names = [p["name"] for p in r.json()]
        assert persona_payload["name"] in names

    async def test_multiple_personas_all_listed(self, http_client):
        for i in range(3):
            await _create_persona(http_client, {"name": f"Persona {i}"})
        r = await http_client.get("/api/v1/personas")
        assert len(r.json()) >= 3


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

class TestUpdatePersona:
    async def test_update_returns_200(self, http_client, persona_payload):
        created = await _create_persona(http_client, persona_payload)
        updated_payload = {**persona_payload, "name": "Updated Name", "id": created["id"]}
        r = await http_client.put(f"/api/v1/personas/{created['id']}", json=updated_payload)
        assert r.status_code == 200

    async def test_update_reflects_new_name(self, http_client, persona_payload):
        created = await _create_persona(http_client, persona_payload)
        updated_payload = {**persona_payload, "name": "Renamed Persona", "id": created["id"]}
        r = await http_client.put(f"/api/v1/personas/{created['id']}", json=updated_payload)
        assert r.json()["name"] == "Renamed Persona"

    async def test_update_nonexistent_returns_404(self, http_client, persona_payload):
        import uuid
        r = await http_client.put(
            f"/api/v1/personas/{uuid.uuid4()}",
            json={**persona_payload, "id": str(uuid.uuid4())},
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

class TestDeletePersona:
    async def test_delete_returns_200(self, http_client, persona_payload):
        created = await _create_persona(http_client, persona_payload)
        r = await http_client.delete(f"/api/v1/personas/{created['id']}")
        assert r.status_code == 200
        assert r.json() == {"deleted": True}

    async def test_deleted_persona_not_found(self, http_client, persona_payload):
        created = await _create_persona(http_client, persona_payload)
        await http_client.delete(f"/api/v1/personas/{created['id']}")
        r = await http_client.get(f"/api/v1/personas/{created['id']}")
        assert r.status_code == 404

    async def test_delete_nonexistent_returns_404(self, http_client):
        import uuid
        r = await http_client.delete(f"/api/v1/personas/{uuid.uuid4()}")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Blend
# ---------------------------------------------------------------------------

class TestBlendPersonas:
    async def test_blend_returns_200(self, http_client):
        p1 = await _create_persona(http_client, {"name": "P1", "creativity": 0.2})
        p2 = await _create_persona(http_client, {"name": "P2", "creativity": 0.8})
        r = await http_client.post(
            "/api/v1/personas/blend",
            json={"persona1_id": p1["id"], "persona2_id": p2["id"], "ratio": 0.5},
        )
        assert r.status_code == 200

    async def test_blend_interpolates_knobs(self, http_client):
        p1 = await _create_persona(http_client, {"name": "P1", "creativity": 0.0})
        p2 = await _create_persona(http_client, {"name": "P2", "creativity": 1.0})
        r = await http_client.post(
            "/api/v1/personas/blend",
            json={"persona1_id": p1["id"], "persona2_id": p2["id"], "ratio": 0.5},
        )
        assert abs(r.json()["creativity"] - 0.5) < 0.05

    async def test_blend_missing_persona_returns_404(self, http_client, persona_payload):
        import uuid
        p1 = await _create_persona(http_client, persona_payload)
        r = await http_client.post(
            "/api/v1/personas/blend",
            json={"persona1_id": p1["id"], "persona2_id": str(uuid.uuid4()), "ratio": 0.5},
        )
        assert r.status_code == 404


class TestBlendMultiplePersonas:
    async def test_preview_blend_returns_200_without_saving(self, http_client):
        p1 = await _create_persona(http_client, {"name": "P1", "creativity": 0.0})
        p2 = await _create_persona(http_client, {"name": "P2", "creativity": 0.5})
        p3 = await _create_persona(http_client, {"name": "P3", "creativity": 1.0})

        before = await http_client.get("/api/v1/personas")
        r = await http_client.post(
            "/api/v1/personas/blend/preview",
            json={"persona_ids": [p1["id"], p2["id"], p3["id"]], "weights": [1, 1, 2]},
        )
        after = await http_client.get("/api/v1/personas")

        assert r.status_code == 200, r.text
        assert abs(r.json()["creativity"] - 0.625) < 0.001
        assert len(after.json()) == len(before.json())

    async def test_multi_persona_blend_saves_custom_name(self, http_client):
        p1 = await _create_persona(http_client, {"name": "P1", "creativity": 0.0})
        p2 = await _create_persona(http_client, {"name": "P2", "creativity": 1.0})
        p3 = await _create_persona(http_client, {"name": "P3", "creativity": 0.5})

        r = await http_client.post(
            "/api/v1/personas/blend",
            json={
                "persona_ids": [p1["id"], p2["id"], p3["id"]],
                "weights": [0.25, 0.5, 0.25],
                "name": "Saved Multi Blend",
                "description": "Custom blend description",
            },
        )

        assert r.status_code == 200, r.text
        body = r.json()
        assert body["name"] == "Saved Multi Blend"
        assert body["description"] == "Custom blend description"
        assert abs(body["creativity"] - 0.625) < 0.001

        listed = await http_client.get("/api/v1/personas")
        assert "Saved Multi Blend" in [persona["name"] for persona in listed.json()]

    async def test_multi_persona_blend_validates_weight_count(self, http_client):
        p1 = await _create_persona(http_client, {"name": "P1"})
        p2 = await _create_persona(http_client, {"name": "P2"})

        r = await http_client.post(
            "/api/v1/personas/blend",
            json={"persona_ids": [p1["id"], p2["id"]], "weights": [1.0]},
        )

        assert r.status_code == 400

    async def test_multi_persona_blend_rejects_non_positive_weights(self, http_client):
        p1 = await _create_persona(http_client, {"name": "P1"})
        p2 = await _create_persona(http_client, {"name": "P2"})

        r = await http_client.post(
            "/api/v1/personas/blend/preview",
            json={"persona_ids": [p1["id"], p2["id"]], "weights": [1.0, 0.0]},
        )

        assert r.status_code == 400


class TestHealthEndpoint:
    async def test_health_is_independent_of_cyrex(self, http_client, monkeypatch):
        import importlib

        main = importlib.import_module("persola.api.main")

        async def fake_check_db_health():
            return True

        async def fail_if_called():
            raise AssertionError("health endpoint should not call cyrex")

        monkeypatch.setattr(main, "check_db_health", fake_check_db_health)
        monkeypatch.setattr(main.cyrex_client, "is_available", fail_if_called)

        r = await http_client.get("/health")

        assert r.status_code == 200
        assert "cyrex_available" not in r.json()
        assert r.json()["database"] is True

    async def test_cyrex_status_gracefully_reports_unconfigured(self, http_client, monkeypatch):
        import importlib

        main = importlib.import_module("persola.api.main")

        monkeypatch.setattr(main.cyrex_client, "base_url", "")
        monkeypatch.setattr(main.cyrex_client, "api_key", "")

        r = await http_client.get("/api/v1/cyrex/status")

        assert r.status_code == 200
        assert r.json()["available"] is False
        assert r.json()["configured"] is False
