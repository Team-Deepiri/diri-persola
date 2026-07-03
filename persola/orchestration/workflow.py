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


@dataclass
class WorkflowChain:
    goal: str
    steps: List[DelegationStep] = field(default_factory=list)

    def add(self, role: str, task: str, depends_on: Optional[List[str]] = None) -> None:
        self.steps.append(DelegationStep(role=role, task=task, depends_on=depends_on or []))


async def execute_workflow_chain(
    chain: WorkflowChain,
    llm_fn: LLMFn,
    *,
    system_prompt_for_role: Callable[[str], str],
    tool_runner: Optional[Callable[[str, str], Awaitable[List[Dict]]]] = None,
) -> WorkflowState:
    state = WorkflowState(goal=chain.goal)
    completed: Dict[str, str] = {}

    for step in chain.steps:
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

    state.complete()
    return state
