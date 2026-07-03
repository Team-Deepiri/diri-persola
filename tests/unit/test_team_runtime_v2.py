"""Expanded tests for team runtime v2."""

import pytest

from persola.engine import PersonaEngine
from persola.models import PersonaProfile
from persola.orchestration.memory import GLOBAL_MEMORY, MemoryStore
from persola.orchestration.parallel import ParallelToolExecutor
from persola.orchestration.personalities import PersonalityRole
from persola.orchestration.router import route_task, select_delegation_plan
from persola.orchestration.team import TeamOrchestrator
from persola.orchestration.tools import ToolRegistry, build_default_registry
from persola.orchestration.workflow import WorkflowChain, execute_workflow_chain_parallel
from persola.services.team_service import TeamService


@pytest.fixture(autouse=True)
def _clear_memory():
    GLOBAL_MEMORY._sessions.clear()
    yield
    GLOBAL_MEMORY._sessions.clear()


class TestRouter:
    def test_routes_analytical_task_to_analyst(self):
        ranked = route_task("analyze metrics and compare evidence", top_k=1)
        assert ranked[0][0] == PersonalityRole.ANALYST

    def test_delegation_plan_includes_coordinator(self):
        plan = select_delegation_plan("brainstorm a creative product launch plan")
        assert plan["coordinator"] == "coordinator"
        assert len(plan["specialists"]) >= 1


class TestParallelWorkflow:
    @pytest.mark.asyncio
    async def test_parallel_specialist_group(self):
        calls = []

        async def fake_llm(system: str, user: str) -> str:
            calls.append(system[:30])
            return f"out-{system[:8]}"

        chain = WorkflowChain(goal="test")
        chain.add("analyst", "analyze", parallel_group="spec")
        chain.add("creative", "ideate", parallel_group="spec")
        chain.add("coordinator", "synthesize", depends_on=["analyst", "creative"])

        wf = await execute_workflow_chain_parallel(
            chain,
            fake_llm,
            system_prompt_for_role=lambda r: r,
        )
        assert len(wf.steps) == 3
        assert wf.status == "completed"


class TestParallelToolExecutor:
    @pytest.mark.asyncio
    async def test_batch_execution(self):
        registry = build_default_registry("pexec-1")
        executor = ParallelToolExecutor(max_concurrency=4)
        registry._executor = executor  # type: ignore[attr-defined]
        results = await executor.run_batch(
            registry,
            [
                {"name": "memory_store", "args": {"key": "a", "value": "1"}},
                {"name": "memory_store", "args": {"key": "b", "value": "2"}},
            ],
        )
        assert len(results) == 2
        assert all(r.success for r in results)


class TestTeamOrchestrator:
    @pytest.mark.asyncio
    async def test_langgraph_path(self):
        async def fake_llm(system: str, user: str) -> str:
            if "coordinator" in system.lower():
                return "Final team answer"
            return "Specialist view"

        orchestrator = TeamOrchestrator(
            llm_fn=fake_llm,
            persona_profile=PersonaProfile(name="Test"),
            use_langgraph=True,
        )
        result = await orchestrator.run("analyze and implement a small API change")
        assert result.response == "Final team answer"
        assert result.runtime_mode == "langgraph"

    @pytest.mark.asyncio
    async def test_chain_path(self):
        async def fake_llm(system: str, user: str) -> str:
            if "coordinator" in system.lower():
                return "Chain synthesis"
            return "step"

        orchestrator = TeamOrchestrator(
            llm_fn=fake_llm,
            use_langgraph=False,
        )
        result = await orchestrator.run("plan a launch")
        assert result.response == "Chain synthesis"
        assert result.runtime_mode == "workflow_chain"


class TestTeamServicePersistence:
    @pytest.mark.asyncio
    async def test_invoke_persists_session_and_workflow(self, db_session):
        async def fake_llm(system: str, user: str) -> str:
            if "coordinator" in system.lower():
                return "Persisted answer"
            return "worker output"

        service = TeamService(db_session)
        result = await service.invoke("design onboarding flow", llm_fn=fake_llm, use_langgraph=False)
        detail = await service.get_session_detail(result.session_id)

        assert detail is not None
        assert detail["message_count"] >= 2
        assert len(detail["workflows"]) >= 1
        assert detail["workflows"][0]["final_response"] == "Persisted answer"


class TestTeamApi:
    @pytest.mark.asyncio
    async def test_runtime_endpoint(self, http_client):
        response = await http_client.get("/api/v1/teams/runtime")
        assert response.status_code == 200
        body = response.json()
        assert "langgraph_available" in body
        assert body["parallel_tools"] is True

    @pytest.mark.asyncio
    async def test_personalities_endpoint(self, http_client):
        response = await http_client.get("/api/v1/teams/personalities")
        assert response.status_code == 200
        assert len(response.json()) >= 5
