"""Integration tests – Agent CRUD and invoke via test HTTP client + SQLite DB."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


pytestmark = pytest.mark.anyio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_agent(client, payload: dict) -> dict:
    r = await client.post("/api/v1/agents", json=payload)
    assert r.status_code == 200, r.text
    return r.json()


async def _create_persona(client, name: str = "Persona") -> dict:
    r = await client.post("/api/v1/personas", json={"name": name})
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

class TestCreateAgent:
    async def test_create_returns_200(self, http_client, agent_payload):
        r = await http_client.post("/api/v1/agents", json=agent_payload)
        assert r.status_code == 200

    async def test_create_response_contains_name(self, http_client, agent_payload):
        body = await _create_agent(http_client, agent_payload)
        assert body["name"] == agent_payload["name"]

    async def test_create_returns_agent_id(self, http_client, agent_payload):
        body = await _create_agent(http_client, agent_payload)
        assert "agent_id" in body and body["agent_id"]

    async def test_create_with_persona_id(self, http_client, agent_payload):
        persona = await _create_persona(http_client)
        payload = {**agent_payload, "persona_id": persona["id"]}
        body = await _create_agent(http_client, payload)
        assert body["persona_id"] == persona["id"]

    async def test_name_too_long_returns_422(self, http_client):
        r = await http_client.post("/api/v1/agents", json={"name": "x" * 201})
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

class TestListAgents:
    async def test_empty_list(self, http_client):
        r = await http_client.get("/api/v1/agents")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    async def test_created_agent_in_list(self, http_client, agent_payload):
        await _create_agent(http_client, agent_payload)
        r = await http_client.get("/api/v1/agents")
        names = [a["name"] for a in r.json()]
        assert agent_payload["name"] in names


# ---------------------------------------------------------------------------
# Get
# ---------------------------------------------------------------------------

class TestGetAgent:
    async def test_get_existing_returns_200(self, http_client, agent_payload):
        created = await _create_agent(http_client, agent_payload)
        r = await http_client.get(f"/api/v1/agents/{created['agent_id']}")
        assert r.status_code == 200

    async def test_get_nonexistent_returns_404(self, http_client):
        import uuid
        r = await http_client.get(f"/api/v1/agents/{uuid.uuid4()}")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

class TestUpdateAgent:
    async def test_update_name_returns_200(self, http_client, agent_payload):
        created = await _create_agent(http_client, agent_payload)
        updated = {**agent_payload, "name": "Updated Agent"}
        r = await http_client.put(f"/api/v1/agents/{created['agent_id']}", json=updated)
        assert r.status_code == 200
        assert r.json()["name"] == "Updated Agent"


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

class TestDeleteAgent:
    async def test_delete_returns_204(self, http_client, agent_payload):
        created = await _create_agent(http_client, agent_payload)
        r = await http_client.delete(f"/api/v1/agents/{created['agent_id']}")
        assert r.status_code == 204

    async def test_deleted_agent_not_found(self, http_client, agent_payload):
        created = await _create_agent(http_client, agent_payload)
        await http_client.delete(f"/api/v1/agents/{created['agent_id']}")
        r = await http_client.get(f"/api/v1/agents/{created['agent_id']}")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Invoke – HAS_CYREX=False path (no LLM required)
# ---------------------------------------------------------------------------

class TestInvokeAgent:
    async def test_invoke_without_cyrex_returns_200(self, http_client, agent_payload):
        """When HAS_CYREX is False the handler returns a degraded 200 response."""
        created = await _create_agent(http_client, agent_payload)

        import persola.api.main as api_module
        with patch.object(api_module, "HAS_CYREX", False):
            r = await http_client.post(
                f"/api/v1/agents/{created['agent_id']}/invoke",
                json={"message": "Hello!"},
            )
        assert r.status_code == 200

    async def test_invoke_response_contains_message_echo(self, http_client, agent_payload):
        created = await _create_agent(http_client, agent_payload)

        import persola.api.main as api_module
        with patch.object(api_module, "HAS_CYREX", False):
            r = await http_client.post(
                f"/api/v1/agents/{created['agent_id']}/invoke",
                json={"message": "Ping"},
            )
        assert r.json()["message"] == "Ping"

    async def test_invoke_nonexistent_agent_returns_404(self, http_client):
        import uuid
        r = await http_client.post(
            f"/api/v1/agents/{uuid.uuid4()}/invoke",
            json={"message": "Hi"},
        )
        assert r.status_code == 404

    async def test_invoke_with_mock_llm_returns_response(self, http_client, agent_payload):
        """With a mocked LLM provider, invoke returns the generated text."""
        created = await _create_agent(http_client, agent_payload)

        mock_llm = MagicMock()
        mock_llm.is_available.return_value = True
        mock_llm.generate = AsyncMock(return_value="I am a mock response.")
        mock_llm.get_provider_type = MagicMock(return_value="mock")

        import persola.api.main as api_module
        with (
            patch.object(api_module, "HAS_CYREX", True),
            patch.object(api_module, "get_llm_provider", return_value=mock_llm),
        ):
            r = await http_client.post(
                f"/api/v1/agents/{created['agent_id']}/invoke",
                json={"message": "What is 2+2?"},
            )
        assert r.status_code == 200
        assert r.json()["response"] == "I am a mock response."

    async def test_invoke_message_too_long_returns_422(self, http_client, agent_payload):
        created = await _create_agent(http_client, agent_payload)
        r = await http_client.post(
            f"/api/v1/agents/{created['agent_id']}/invoke",
            json={"message": "x" * 32_769},
        )
        assert r.status_code == 422
