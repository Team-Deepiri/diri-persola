"""
End-to-end workflow test: create persona → create agent → invoke → check history.

Uses the same SQLite in-memory database as the integration tests (see root
conftest.py).  LLM calls are mocked so no external services are required.

To run against a real PostgreSQL instance instead, set:
    DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/persola_test
before running pytest.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


pytestmark = pytest.mark.anyio


class TestFullWorkflow:
    """
    Scenario:
        1. Create a persona with custom knobs.
        2. Create an agent that references the persona.
        3. Invoke the agent twice (same session) with a mocked LLM.
        4. Verify the session and both messages are persisted.
        5. Verify the second invocation references the same session.
    """

    async def test_create_persona_to_message_history(self, http_client):
        # ── 1. Create Persona ────────────────────────────────────────────
        persona_r = await http_client.post(
            "/api/v1/personas",
            json={
                "name": "E2E Persona",
                "description": "Used in end-to-end workflow test",
                "creativity": 0.7,
                "formality": 0.4,
                "verbosity": 0.6,
            },
        )
        assert persona_r.status_code == 200, persona_r.text
        persona = persona_r.json()
        assert persona["name"] == "E2E Persona"
        persona_id = persona["id"]

        # ── 2. Create Agent linked to Persona ────────────────────────────
        agent_r = await http_client.post(
            "/api/v1/agents",
            json={
                "name": "E2E Agent",
                "model": "llama3:8b",
                "temperature": 0.7,
                "persona_id": persona_id,
            },
        )
        assert agent_r.status_code == 200, agent_r.text
        agent = agent_r.json()
        agent_id = agent["agent_id"]
        assert agent["persona_id"] == persona_id

        # ── 3. Invoke twice (same session) with a mocked LLM ─────────────
        mock_llm = MagicMock()
        mock_llm.is_available.return_value = True
        mock_llm.generate = AsyncMock(side_effect=["First reply.", "Second reply."])
        mock_llm.get_provider_type = MagicMock(return_value="mock")

        import persola.api.main as api_module
        with (
            patch.object(api_module, "HAS_CYREX", True),
            patch.object(api_module, "get_llm_provider", return_value=mock_llm),
        ):
            invoke1_r = await http_client.post(
                f"/api/v1/agents/{agent_id}/invoke",
                json={"message": "Tell me about yourself.", "session_id": "e2e-session"},
            )
            invoke2_r = await http_client.post(
                f"/api/v1/agents/{agent_id}/invoke",
                json={"message": "What can you help with?", "session_id": "e2e-session"},
            )

        assert invoke1_r.status_code == 200
        assert invoke2_r.status_code == 200
        assert invoke1_r.json()["response"] == "First reply."
        assert invoke2_r.json()["response"] == "Second reply."

        # ── 4. Verify exactly one session was created ─────────────────────
        sessions_r = await http_client.get(f"/api/v1/agents/{agent_id}/sessions")
        assert sessions_r.status_code == 200
        sessions = sessions_r.json()
        assert len(sessions) == 1, f"Expected 1 session, got {len(sessions)}"

        session = sessions[0]
        assert session["session_id"] == "e2e-session"

        # ── 5. Verify message history is persisted ────────────────────────
        messages_r = await http_client.get(f"/api/v1/sessions/e2e-session/messages")
        assert messages_r.status_code == 200
        messages = messages_r.json()

        # 2 invocations × (1 user + 1 assistant) = 4 messages
        assert len(messages) == 4, f"Expected 4 messages, got {len(messages)}"

        roles = [m["role"] for m in messages]
        assert roles.count("user") == 2
        assert roles.count("assistant") == 2

        user_messages = [m["content"] for m in messages if m["role"] == "user"]
        assert "Tell me about yourself." in user_messages
        assert "What can you help with?" in user_messages

    async def test_persona_system_prompt_endpoint(self, http_client):
        """system-prompt endpoint returns non-empty text based on persona knobs."""
        persona_r = await http_client.post(
            "/api/v1/personas",
            json={"name": "SysPrompt Persona", "creativity": 0.8, "formality": 0.2},
        )
        persona_id = persona_r.json()["id"]
        r = await http_client.get(f"/api/v1/personas/{persona_id}/system-prompt")
        assert r.status_code == 200
        assert len(r.json()["system_prompt"]) > 0

    async def test_persona_export_import_roundtrip(self, http_client):
        """Export a persona and re-import it; knob values must be preserved."""
        original_r = await http_client.post(
            "/api/v1/personas",
            json={"name": "Export Test", "creativity": 0.77, "humor": 0.33},
        )
        original = original_r.json()
        export_r = await http_client.get(f"/api/v1/personas/{original['id']}/export")
        assert export_r.status_code == 200
        exported = export_r.json()

        # Strip the old id so a new one is assigned.
        exported.pop("id", None)
        exported["name"] = "Imported Copy"

        import_r = await http_client.post("/api/v1/personas/import", json=exported)
        assert import_r.status_code == 200
        imported = import_r.json()
        assert abs(imported["creativity"] - 0.77) < 0.001
        assert abs(imported["humor"] - 0.33) < 0.001
