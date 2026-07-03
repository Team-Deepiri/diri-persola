"""LangGraph-based team workflow when langgraph is installed."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, List, Optional, TypedDict

LLMFn = Callable[[str, str], Awaitable[str]]


class TeamGraphState(TypedDict, total=False):
    task: str
    specialists: List[str]
    specialist_outputs: Dict[str, str]
    coordinator_output: str
    tool_results: List[Dict[str, Any]]


def langgraph_available() -> bool:
    try:
        import langgraph  # noqa: F401

        return True
    except ImportError:
        return False


async def run_langgraph_team(
    task: str,
    specialists: List[str],
    llm_fn: LLMFn,
    system_prompt_for_role: Callable[[str], str],
    tool_runner: Optional[Callable[[str, str], Awaitable[List[Dict[str, Any]]]]] = None,
) -> TeamGraphState:
    """Execute specialist nodes in parallel, then coordinator synthesis via LangGraph."""
    if not langgraph_available():
        return await _fallback_parallel_team(task, specialists, llm_fn, system_prompt_for_role, tool_runner)

    from langgraph.graph import END, StateGraph

    async def specialists_node(state: TeamGraphState) -> TeamGraphState:
        outputs: Dict[str, str] = {}
        tool_results: List[Dict[str, Any]] = []

        async def _run_role(role: str) -> None:
            system = system_prompt_for_role(role)
            user = f"As {role}, contribute your perspective on: {state['task']}"
            outputs[role] = await llm_fn(system, user)
            if tool_runner:
                tool_results.extend(await tool_runner(role, outputs[role]))

        import asyncio

        await asyncio.gather(*[_run_role(role) for role in state["specialists"]])
        return {
            **state,
            "specialist_outputs": outputs,
            "tool_results": tool_results,
        }

    async def coordinator_node(state: TeamGraphState) -> TeamGraphState:
        context = "\n\n".join(
            f"### {role}\n{output}" for role, output in state.get("specialist_outputs", {}).items()
        )
        system = system_prompt_for_role("coordinator")
        user = f"Synthesize the team's work.\n\nTask: {state['task']}\n\nTeam input:\n{context}"
        response = await llm_fn(system, user)
        return {**state, "coordinator_output": response}

    graph = StateGraph(TeamGraphState)
    graph.add_node("specialists", specialists_node)
    graph.add_node("coordinator", coordinator_node)
    graph.set_entry_point("specialists")
    graph.add_edge("specialists", "coordinator")
    graph.add_edge("coordinator", END)
    app = graph.compile()

    initial: TeamGraphState = {"task": task, "specialists": specialists, "specialist_outputs": {}, "tool_results": []}
    final = await app.ainvoke(initial)
    return final


async def _fallback_parallel_team(
    task: str,
    specialists: List[str],
    llm_fn: LLMFn,
    system_prompt_for_role: Callable[[str], str],
    tool_runner: Optional[Callable[[str, str], Awaitable[List[Dict[str, Any]]]]],
) -> TeamGraphState:
    import asyncio

    outputs: Dict[str, str] = {}
    tool_results: List[Dict[str, Any]] = []

    async def _run(role: str) -> None:
        outputs[role] = await llm_fn(
            system_prompt_for_role(role),
            f"As {role}, contribute your perspective on: {task}",
        )
        if tool_runner:
            tool_results.extend(await tool_runner(role, outputs[role]))

    await asyncio.gather(*[_run(r) for r in specialists])
    context = "\n\n".join(f"### {role}\n{out}" for role, out in outputs.items())
    coordinator_output = await llm_fn(
        system_prompt_for_role("coordinator"),
        f"Synthesize the team's work.\n\nTask: {task}\n\nTeam input:\n{context}",
    )
    return {
        "task": task,
        "specialists": specialists,
        "specialist_outputs": outputs,
        "coordinator_output": coordinator_output,
        "tool_results": tool_results,
    }
