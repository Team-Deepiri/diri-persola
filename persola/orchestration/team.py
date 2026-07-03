"""Team orchestrator — multi-personality delegation with parallel tools and LangGraph."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional

from persola.engine import PersonaEngine
from persola.models import PersonaProfile

from .langgraph_runtime import run_langgraph_team
from .memory import GLOBAL_MEMORY
from .personalities import BUILTIN_ARCHETYPES, PersonalityRole
from .router import select_delegation_plan
from .state import TeamSessionState, WorkflowState
from .tools import ToolRegistry, build_default_registry
from .workflow import WorkflowChain, execute_workflow_chain_parallel

LLMFn = Callable[[str, str], Awaitable[str]]


@dataclass
class TeamRunResult:
    session_id: str
    response: str
    workflow: WorkflowState
    delegation_plan: Dict[str, Any]
    session: TeamSessionState
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    personalities_used: List[str] = field(default_factory=list)
    runtime_mode: str = "langgraph"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "response": self.response,
            "workflow": self.workflow.to_dict(),
            "delegation_plan": self.delegation_plan,
            "session": self.session.to_dict(),
            "tool_results": self.tool_results,
            "personalities_used": self.personalities_used,
            "runtime_mode": self.runtime_mode,
        }


class TeamOrchestrator:
    """Coordinates specialist personalities like a human team."""

    def __init__(
        self,
        llm_fn: LLMFn,
        persona_profile: Optional[PersonaProfile] = None,
        tool_registry: Optional[ToolRegistry] = None,
        use_langgraph: bool = True,
    ) -> None:
        self.llm_fn = llm_fn
        self.persona_engine = PersonaEngine()
        self.base_profile = persona_profile or PersonaProfile(name="Team Default")
        self._tool_registry = tool_registry
        self.use_langgraph = use_langgraph

    def _system_prompt_for_role(self, role_key: str) -> str:
        try:
            role = PersonalityRole(role_key)
        except ValueError:
            return self.persona_engine.build_system_prompt(self.base_profile)
        archetype = BUILTIN_ARCHETYPES[role]
        blended = PersonaProfile(
            name=archetype.name,
            description=archetype.tagline,
            **{**self.base_profile.get_knobs(), **archetype.knob_overrides},
        )
        base = self.persona_engine.build_system_prompt(blended)
        return f"{base}\n\n## Team role\n{archetype.system_directive}\n\nCollaboration style: {archetype.collaboration_style}"

    async def _make_tool_runner(self, registry: ToolRegistry) -> Callable[[str, str], Awaitable[List[Dict[str, Any]]]]:
        async def runner(role: str, output: str) -> List[Dict[str, Any]]:
            calls = [
                {"name": "memory_store", "args": {"key": f"{role}:latest", "value": output[:2000], "source_role": role}},
                {"name": "delegate_subtask", "args": {"role": "executor", "subtask": output[:500]}},
            ]
            executor = getattr(registry, "_executor", None)
            if executor is not None:
                batch = await executor.run_batch(registry, calls)
                return [
                    {"name": r.name, "success": r.success, "result": r.result, "error": r.error, "duration_ms": r.duration_ms}
                    for r in batch
                ]
            return await registry.run_parallel(calls)

        return runner

    async def _run_langgraph_path(
        self,
        task: str,
        specialists: List[str],
        session: TeamSessionState,
        registry: ToolRegistry,
    ) -> TeamRunResult:
        tool_runner = await self._make_tool_runner(registry)
        graph_state = await run_langgraph_team(
            task,
            specialists,
            self.llm_fn,
            self._system_prompt_for_role,
            tool_runner=tool_runner,
        )

        workflow = WorkflowState(goal=task)
        for role, output in graph_state.get("specialist_outputs", {}).items():
            workflow.add_step(role, f"As {role}, contribute on: {task}", output, tool_calls=[])
        coordinator_output = graph_state.get("coordinator_output", "")
        workflow.add_step(
            PersonalityRole.COORDINATOR.value,
            f"Synthesize team work for: {task}",
            coordinator_output,
        )
        workflow.complete()

        session.active_workflow = workflow
        session.memory_snapshot = GLOBAL_MEMORY.snapshot(session.session_id)
        session.append_message("assistant", coordinator_output)

        tool_results = graph_state.get("tool_results", [])
        personalities_used = list(graph_state.get("specialist_outputs", {}).keys()) + [PersonalityRole.COORDINATOR.value]

        return TeamRunResult(
            session_id=session.session_id,
            response=coordinator_output,
            workflow=workflow,
            delegation_plan=select_delegation_plan(task),
            session=session,
            tool_results=tool_results,
            personalities_used=personalities_used,
            runtime_mode="langgraph",
        )

    async def _run_chain_path(
        self,
        task: str,
        specialists: List[str],
        session: TeamSessionState,
        registry: ToolRegistry,
    ) -> TeamRunResult:
        chain = WorkflowChain(goal=task)
        for spec_role in specialists:
            archetype = BUILTIN_ARCHETYPES[PersonalityRole(spec_role)]
            chain.add(
                spec_role,
                f"As {archetype.name}, contribute your perspective on: {task}",
                depends_on=[],
                parallel_group="specialists",
            )
        chain.add(
            PersonalityRole.COORDINATOR.value,
            f"Synthesize the team's work into one cohesive answer for the user.\n\nUser task: {task}",
            depends_on=specialists,
        )

        tool_runner = await self._make_tool_runner(registry)
        workflow = await execute_workflow_chain_parallel(
            chain,
            self.llm_fn,
            system_prompt_for_role=self._system_prompt_for_role,
            tool_runner=tool_runner,
        )

        coordinator_output = workflow.steps[-1].output if workflow.steps else ""
        session.active_workflow = workflow
        session.memory_snapshot = GLOBAL_MEMORY.snapshot(session.session_id)
        session.append_message("assistant", coordinator_output)

        tool_results: List[Dict[str, Any]] = []
        for step in workflow.steps:
            tool_results.extend(step.tool_calls)

        return TeamRunResult(
            session_id=session.session_id,
            response=coordinator_output,
            workflow=workflow,
            delegation_plan=select_delegation_plan(task),
            session=session,
            tool_results=tool_results,
            personalities_used=[s.role for s in workflow.steps],
            runtime_mode="workflow_chain",
        )

    async def run(self, task: str, session: Optional[TeamSessionState] = None) -> TeamRunResult:
        session = session or TeamSessionState()
        session.append_message("user", task)
        plan = select_delegation_plan(task)
        specialists: List[str] = plan["specialists"]  # type: ignore[assignment]

        registry = self._tool_registry or build_default_registry(session.session_id)

        if self.use_langgraph:
            return await self._run_langgraph_path(task, specialists, session, registry)
        return await self._run_chain_path(task, specialists, session, registry)
