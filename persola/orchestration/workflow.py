"""Workflow chaining and step delegation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Awaitable, Callable, Dict, List, Optional

from .state import WorkflowState


LLMFn = Callable[[str, str], Awaitable[str]]


@dataclass
class DelegationStep:
    role: str
    task: str
    depends_on: List[str] = field(default_factory=list)
    parallel_group: Optional[str] = None


@dataclass
class WorkflowChain:
    goal: str
    steps: List[DelegationStep] = field(default_factory=list)

    def add(
        self,
        role: str,
        task: str,
        depends_on: Optional[List[str]] = None,
        parallel_group: Optional[str] = None,
    ) -> None:
        self.steps.append(
            DelegationStep(role=role, task=task, depends_on=depends_on or [], parallel_group=parallel_group)
        )


async def execute_workflow_chain(
    chain: WorkflowChain,
    llm_fn: LLMFn,
    *,
    system_prompt_for_role: Callable[[str], str],
    tool_runner: Optional[Callable[[str, str], Awaitable[List[Dict]]]] = None,
) -> WorkflowState:
    return await execute_workflow_chain_parallel(
        chain,
        llm_fn,
        system_prompt_for_role=system_prompt_for_role,
        tool_runner=tool_runner,
    )


async def execute_workflow_chain_parallel(
    chain: WorkflowChain,
    llm_fn: LLMFn,
    *,
    system_prompt_for_role: Callable[[str], str],
    tool_runner: Optional[Callable[[str, str], Awaitable[List[Dict]]]] = None,
) -> WorkflowState:
    import asyncio

    state = WorkflowState(goal=chain.goal)
    completed: Dict[str, str] = {}
    i = 0

    while i < len(chain.steps):
        step = chain.steps[i]
        group = step.parallel_group
        if group:
            group_steps = [step]
            j = i + 1
            while j < len(chain.steps) and chain.steps[j].parallel_group == group:
                group_steps.append(chain.steps[j])
                j += 1

            async def _run_one(s: DelegationStep) -> tuple[str, str, List[Dict]]:
                context_bits = []
                for dep in s.depends_on:
                    if dep in completed:
                        context_bits.append(f"[{dep}]: {completed[dep]}")
                context = "\n".join(context_bits)
                prompt = s.task if not context else f"{s.task}\n\nPrior context:\n{context}"
                system = system_prompt_for_role(s.role)
                output = await llm_fn(system, prompt)
                tool_calls: List[Dict] = []
                if tool_runner is not None:
                    tool_calls = await tool_runner(s.role, output)
                return s.role, output, tool_calls

            results = await asyncio.gather(*[_run_one(s) for s in group_steps])
            for role, output, tool_calls in results:
                matching = next(s for s in group_steps if s.role == role)
                state.add_step(role, matching.task, output, tool_calls=tool_calls)
                completed[role] = output
            i = j
            continue

        context_bits = []
        for dep in step.depends_on:
            if dep in completed:
                context_bits.append(f"[{dep}]: {completed[dep]}")
        context = "\n".join(context_bits)
        prompt = step.task if not context else f"{step.task}\n\nPrior context:\n{context}"
        system = system_prompt_for_role(step.role)
        output = await llm_fn(system, prompt)

        tool_calls: List[Dict] = []
        if tool_runner is not None:
            tool_calls = await tool_runner(step.role, output)

        state.add_step(step.role, step.task, output, tool_calls=tool_calls)
        completed[step.role] = output
        i += 1

    state.complete()
    return state
