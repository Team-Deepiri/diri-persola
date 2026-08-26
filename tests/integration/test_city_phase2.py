"""Phase 2 — sandbox, structured tool calls, city build/run tools."""

from __future__ import annotations

from uuid import UUID

import pytest

from persola.orchestration.sandbox import (
    SandboxError,
    run_python_sandboxed,
    sanitize_workspace_path,
)
from persola.orchestration.tool_calls import parse_tool_calls
from persola.orchestration.tools import ToolRegistry
from persola.services.city_service import CityService

pytestmark = pytest.mark.anyio


class TestSandboxPaths:
    def test_rejects_parent_escape(self):
        with pytest.raises(SandboxError):
            sanitize_workspace_path("../etc/passwd")

    def test_rejects_absolute(self):
        with pytest.raises(SandboxError):
            sanitize_workspace_path("/tmp/x.py")

    def test_normalizes_relative(self):
        assert sanitize_workspace_path("./src/hello.py") == "src/hello.py"


class TestSandboxedPython:
    async def test_runs_trivial_script(self):
        result = await run_python_sandboxed(source="print('city-ok')\n", filename="hello.py")
        assert result["status"] == "succeeded"
        assert "city-ok" in result["stdout"]

    async def test_timeout(self):
        result = await run_python_sandboxed(
            source="import time\ntime.sleep(5)\n",
            filename="slow.py",
            timeout_s=0.2,
        )
        assert result["status"] == "timeout"


class TestParseToolCalls:
    def test_json_tool_calls_block(self):
        text = """
Here is my plan.
```json
{"tool_calls": [{"name": "workspace_write", "args": {"path": "a.py", "content": "print(1)"}}]}
```
"""
        calls = parse_tool_calls(text)
        assert calls[0]["name"] == "workspace_write"
        assert calls[0]["args"]["path"] == "a.py"

    def test_tool_call_line(self):
        calls = parse_tool_calls('TOOL_CALL: run_python({"path": "a.py"})')
        assert calls == [{"name": "run_python", "args": {"path": "a.py"}}]

    def test_empty_and_whitespace(self):
        assert parse_tool_calls("") == []
        assert parse_tool_calls("   \n") == []

    def test_malformed_whole_message_json_returns_empty(self):
        assert parse_tool_calls("{not-json") == []

    def test_malformed_fence_ignored_tool_line_kept(self):
        text = """
```json
{broken
```
TOOL_CALL: memory_store({"key": "k", "value": "v"})
"""
        calls = parse_tool_calls(text)
        assert calls == [{"name": "memory_store", "args": {"key": "k", "value": "v"}}]

    def test_tool_line_with_bad_args_keeps_name(self):
        calls = parse_tool_calls("TOOL_CALL: emit_viz_event({not-json})")
        assert calls == [{"name": "emit_viz_event", "args": {}}]

    def test_single_object_without_tool_calls_key(self):
        calls = parse_tool_calls('{"name": "workspace_list", "args": {"path": "."}}')
        assert calls == [{"name": "workspace_list", "args": {"path": "."}}]

    def test_dedupes_identical_calls(self):
        text = """
{"tool_calls":[{"name":"echo","args":{"x":1}}]}
TOOL_CALL: echo({"x": 1})
"""
        calls = parse_tool_calls(text)
        assert calls == [{"name": "echo", "args": {"x": 1}}]


class TestCityBuildRunFlow:
    async def test_write_read_run_succeeds(self, db_session):
        service = CityService(db_session)
        family = await service.create_family(name="Build Family", parent_name="Parent")
        family_id = UUID(family["id"])
        agent_id = UUID(family["members"][0]["agent_id"])
        job = await service.start_job(family_id=family_id, goal="build and run hello")
        job_id = UUID(job["id"])

        result = await service.execute_tool_calls(
            job_id,
            [
                {
                    "name": "workspace_write",
                    "args": {"path": "hello.py", "content": "print('hello-city')\n"},
                },
                {"name": "workspace_read", "args": {"path": "hello.py"}},
                {"name": "run_python", "args": {"path": "hello.py"}},
            ],
            agent_id=agent_id,
        )

        assert len(result["tool_results"]) == 3
        assert result["tool_results"][0]["ok"] is True
        assert result["tool_results"][1]["result"]["found"] is True
        run_result = result["tool_results"][2]["result"]
        assert run_result["ok"] is True
        assert run_result["result"]["status"] == "succeeded"
        assert "hello-city" in (run_result["result"]["stdout"] or "")

        runs = await service.list_runs(job_id)
        assert any(r["status"] == "succeeded" and r["tool"] == "run_python" for r in runs)
        arts = await service.list_artifacts(job_id)
        assert any(a["path"] == "hello.py" for a in arts)

    async def test_path_escape_denied_via_tool(self, db_session):
        service = CityService(db_session)
        family = await service.create_family(name="Escape Family")
        job = await service.start_job(family_id=UUID(family["id"]), goal="escape")
        result = await service.execute_tool_calls(
            UUID(job["id"]),
            [{"name": "workspace_write", "args": {"path": "../secret.py", "content": "x"}}],
        )
        assert result["tool_results"][0]["ok"] is False


class TestCityBuildRunAPI:
    async def test_invoke_build_and_run(self, http_client):
        fam = await http_client.post("/api/v1/city/families", json={"name": "API Builders"})
        assert fam.status_code == 200, fam.text
        family = fam.json()
        job_r = await http_client.post(
            "/api/v1/city/jobs",
            json={"family_id": family["id"], "goal": "write and run"},
        )
        assert job_r.status_code == 200, job_r.text
        job_id = job_r.json()["id"]
        agent_id = family["members"][0]["agent_id"]

        inv = await http_client.post(
            f"/api/v1/city/jobs/{job_id}/invoke",
            json={
                "agent_id": agent_id,
                "complete": True,
                "calls": [
                    {
                        "name": "workspace_write",
                        "args": {"path": "main.py", "content": "print(2+2)\n"},
                    },
                    {"name": "run_python", "args": {"path": "main.py"}},
                    {
                        "name": "emit_viz_event",
                        "args": {"event_type": "viz.pulse", "payload": {"note": "done"}},
                    },
                ],
            },
        )
        assert inv.status_code == 200, inv.text
        body = inv.json()
        assert body["job"]["status"] == "completed"
        assert any(t["name"] == "run_python" and t["ok"] for t in body["invoke"]["tool_results"])

        runs = await http_client.get(f"/api/v1/city/jobs/{job_id}/runs")
        assert runs.status_code == 200
        assert any(r["status"] == "succeeded" for r in runs.json())

    async def test_list_city_tools(self, http_client):
        r = await http_client.get("/api/v1/city/tools")
        assert r.status_code == 200
        names = {t["name"] for t in r.json()}
        assert {
            "workspace_write",
            "workspace_read",
            "workspace_list",
            "run_python",
            "emit_viz_event",
        } <= names


class TestOrchestratorParsesToolCalls:
    async def test_tool_runner_prefers_structured_calls(self):
        from persola.orchestration.team import TeamOrchestrator
        from persola.orchestration.tools import ToolSpec

        ran: list[str] = []

        async def llm(system: str, user: str) -> str:
            return "unused"

        registry = ToolRegistry()

        async def _echo(**kwargs):
            ran.append(str(kwargs.get("text", "")))
            return {"echo": kwargs.get("text", "")}

        async def _store(**kwargs):
            return {"stored": True}

        registry.register(ToolSpec("echo", "echo", _echo))
        registry.register(ToolSpec("memory_store", "mem", _store))
        registry.register(ToolSpec("delegate_subtask", "delegate", _store))

        orch = TeamOrchestrator(llm_fn=llm, tool_registry=registry, use_langgraph=False)
        runner = await orch._make_tool_runner(registry)
        results = await runner(
            "executor",
            '{"tool_calls":[{"name":"echo","args":{"text":"from-executor"}}]}',
        )
        assert ran == ["from-executor"]
        assert (
            results[0]["name"] == "echo"
            or results[0].get("result", {}).get("echo") == "from-executor"
        )
