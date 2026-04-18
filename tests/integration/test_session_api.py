"""Integration tests – Session and message persistence."""

from unittest.mock import patch

import pytest


pytestmark = pytest.mark.anyio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_agent(client, name: str = "Agent") -> dict:
    r = await client.post("/api/v1/agents", json={"name": name, "model": "llama3:8b"})
    assert r.status_code == 200, r.text
    return r.json()


async def _invoke(client, agent_id: str, message: str, session_id: str | None = None) -> dict:
    import persola.api.main as api_module

    payload: dict = {"message": message}
    if session_id:
        payload["session_id"] = session_id

    with patch.object(api_module, "HAS_CYREX", False):
        r = await client.post(f"/api/v1/agents/{agent_id}/invoke", json=payload)
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

class TestAgentSessions:
    async def test_list_sessions_empty_on_fresh_agent(self, http_client):
        agent = await _create_agent(http_client)
        r = await http_client.get(f"/api/v1/agents/{agent['agent_id']}/sessions")
        assert r.status_code == 200
        assert r.json() == []

    async def test_invoke_creates_session(self, http_client):
        agent = await _create_agent(http_client)
        await _invoke(http_client, agent["agent_id"], "Hello")
        r = await http_client.get(f"/api/v1/agents/{agent['agent_id']}/sessions")
        assert len(r.json()) == 1

    async def test_same_session_id_reuses_session(self, http_client):
        agent = await _create_agent(http_client)
        sid = "my-session-1"
        await _invoke(http_client, agent["agent_id"], "First", session_id=sid)
        await _invoke(http_client, agent["agent_id"], "Second", session_id=sid)
        r = await http_client.get(f"/api/v1/agents/{agent['agent_id']}/sessions")
        assert len(r.json()) == 1

    async def test_different_session_ids_create_separate_sessions(self, http_client):
        agent = await _create_agent(http_client)
        await _invoke(http_client, agent["agent_id"], "A", session_id="s1")
        await _invoke(http_client, agent["agent_id"], "B", session_id="s2")
        r = await http_client.get(f"/api/v1/agents/{agent['agent_id']}/sessions")
        assert len(r.json()) == 2

    async def test_session_has_expected_fields(self, http_client):
        agent = await _create_agent(http_client)
        await _invoke(http_client, agent["agent_id"], "Hi", session_id="check-fields")
        r = await http_client.get(f"/api/v1/agents/{agent['agent_id']}/sessions")
        session = r.json()[0]
        for field in ("id", "agent_id", "session_id", "message_count"):
            assert field in session, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

class TestSessionMessages:
    async def _setup_session(self, client, messages: list[str]) -> tuple[dict, str]:
        """Create an agent, invoke with each message, return (agent, session_id_string)."""
        agent = await _create_agent(client)
        sid = "msg-test-session"
        for msg in messages:
            await _invoke(client, agent["agent_id"], msg, session_id=sid)
        # Get the DB session id (UUID) from the sessions list
        r = await client.get(f"/api/v1/agents/{agent['agent_id']}/sessions")
        db_session_id = r.json()[0]["session_id"]
        return agent, db_session_id

    async def test_messages_endpoint_returns_200(self, http_client):
        _, sid = await self._setup_session(http_client, ["Hello"])
        r = await http_client.get(f"/api/v1/sessions/{sid}/messages")
        assert r.status_code == 200

    async def test_messages_count_matches_invocations(self, http_client):
        _, sid = await self._setup_session(http_client, ["One", "Two", "Three"])
        r = await http_client.get(f"/api/v1/sessions/{sid}/messages")
        # Each invoke adds: 1 user message + 1 assistant message = 2 per invoke
        assert len(r.json()) >= 3

    async def test_messages_have_expected_fields(self, http_client):
        _, sid = await self._setup_session(http_client, ["Test"])
        r = await http_client.get(f"/api/v1/sessions/{sid}/messages")
        msg = r.json()[0]
        for field in ("id", "session_id", "role", "content"):
            assert field in msg, f"Missing field: {field}"

    async def test_first_message_role_is_user(self, http_client):
        _, sid = await self._setup_session(http_client, ["Hello"])
        r = await http_client.get(f"/api/v1/sessions/{sid}/messages")
        roles = [m["role"] for m in r.json()]
        assert "user" in roles

    async def test_nonexistent_session_returns_404(self, http_client):
        r = await http_client.get("/api/v1/sessions/nonexistent-session-id/messages")
        assert r.status_code == 404
