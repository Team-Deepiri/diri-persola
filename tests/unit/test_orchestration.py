"""Unit tests for multi-personality team orchestration."""

import pytest

from persola.engine import PersonaEngine
from persola.models import PersonaProfile
from persola.orchestration.memory import GLOBAL_MEMORY, MemoryStore
from persola.orchestration.personalities import PersonalityRole
from persola.orchestration.router import route_task, select_delegation_plan
from persola.orchestration.team import TeamOrchestrator
from persola.orchestration.tools import ToolRegistry, build_default_registry


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


class TestMemoryTools:
    def test_store_and_recall(self):
        store = MemoryStore()
        store.store("s1", "goal", "ship feature")
        assert store.recall("s1", "goal") == "ship feature"

    def test_search_finds_entries(self):
        store = MemoryStore()
        store.store("s1", "note", "user prefers concise answers", tags=["preference"])
        hits = store.search("s1", "concise")
        assert len(hits) == 1


class TestParallelTools:
    @pytest.mark.asyncio
    async def test_run_parallel(self):
        registry = build_default_registry("sess-1")
        results = await registry.run_parallel(
            [
                {"name": "memory_store", "args": {"key": "a", "value": "1"}},
                {"name": "memory_store", "args": {"key": "b", "value": "2"}},
            ]
        )
        assert len(results) == 2
        assert all("result" in r for r in results)
        assert GLOBAL_MEMORY.recall("sess-1", "a") == "1"


class TestTeamOrchestrator:
    @pytest.mark.asyncio
    async def test_team_run_returns_coordinator_synthesis(self):
        calls = []

        async def fake_llm(system: str, user: str) -> str:
            calls.append((system, user))
            if "Coordinator" in system or "coordinator" in system.lower():
                return "Final team answer"
            return f"Perspective from {system[:20]}"

        orchestrator = TeamOrchestrator(
            llm_fn=fake_llm,
            persona_profile=PersonaProfile(name="Test"),
        )
        result = await orchestrator.run("analyze and implement a small API change")

        assert result.response == "Final team answer"
        assert result.workflow.status == "completed"
        assert PersonalityRole.COORDINATOR.value in result.personalities_used
        assert len(calls) >= 2

    def test_blend_multiple_from_pr31(self):
        engine = PersonaEngine()
        p1 = PersonaProfile(name="A", creativity=0.0)
        p2 = PersonaProfile(name="B", creativity=1.0)
        blended = engine.blend_multiple([p1, p2], [1, 1])
        assert abs(blended.creativity - 0.5) < 0.001
