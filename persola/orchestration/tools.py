"""Tool registry with parallel execution for agent teams."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

ToolHandler = Callable[..., Awaitable[dict[str, Any]]]


@dataclass
class ToolSpec:
    name: str
    description: str
    handler: ToolHandler
    parallel_safe: bool = True
    tags: list[str] = field(default_factory=list)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "parallel_safe": t.parallel_safe,
                "tags": t.tags,
            }
            for t in self._tools.values()
        ]

    async def run(self, name: str, **kwargs: Any) -> dict[str, Any]:
        spec = self._tools.get(name)
        if spec is None:
            return {"error": f"Unknown tool: {name}"}
        return await spec.handler(**kwargs)

    async def run_parallel(self, calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Run tool calls; ``parallel_safe=False`` tools execute serially (shared DB safety)."""

        results: list[dict[str, Any] | None] = [None] * len(calls)
        parallel_idx: list[int] = []
        parallel_coros: list[Any] = []

        async def _run(call: dict[str, Any]) -> dict[str, Any]:
            name = call["name"]
            args = call.get("args", {})
            spec = self._tools.get(name)
            if spec is None:
                return {"name": name, "error": "unknown_tool"}
            result = await spec.handler(**args)
            return {"name": name, "result": result}

        for i, call in enumerate(calls):
            spec = self._tools.get(call.get("name", ""))
            if spec is not None and not spec.parallel_safe:
                results[i] = await _run(call)
            else:
                parallel_idx.append(i)
                parallel_coros.append(_run(call))

        if parallel_coros:
            parallel_results = await asyncio.gather(*parallel_coros)
            for i, res in zip(parallel_idx, parallel_results):
                results[i] = res

        return [r if r is not None else {"name": "unknown", "error": "missing"} for r in results]


def build_default_registry(session_id: str, tenant_id: str | None = None) -> ToolRegistry:
    from .memory import memory_recall_tool, memory_search_tool, memory_store_tool

    registry = ToolRegistry()
    tenant_uuid = UUID(tenant_id) if tenant_id else None

    async def _store(**kwargs: Any) -> dict[str, Any]:
        return memory_store_tool(session_id, kwargs["key"], kwargs["value"], tenant_id=tenant_id)

    async def _recall(**kwargs: Any) -> dict[str, Any]:
        return memory_recall_tool(session_id, kwargs["key"], tenant_id=tenant_id)

    async def _search(**kwargs: Any) -> dict[str, Any]:
        return memory_search_tool(session_id, kwargs["query"], tenant_id=tenant_id)

    async def _echo(**kwargs: Any) -> dict[str, Any]:
        return {"echo": kwargs.get("text", "")}

    registry.register(
        ToolSpec("memory_store", "Persist a key/value in team session memory.", _store, tags=["memory"])
    )
    registry.register(
        ToolSpec("memory_recall", "Recall a value from team session memory.", _recall, tags=["memory"])
    )
    registry.register(
        ToolSpec("memory_search", "Search team session memory.", _search, tags=["memory"])
    )
    registry.register(
        ToolSpec("echo", "Echo text (debug / connectivity).", _echo, tags=["utility"])
    )

    async def _delegate(**kwargs: Any) -> dict[str, Any]:
        from .task_queue import GLOBAL_TASK_QUEUE

        role = kwargs.get("role", "executor")
        subtask = kwargs.get("subtask", "")
        task = await GLOBAL_TASK_QUEUE.enqueue(
            team_id=kwargs.get("team_id", "default"),
            role=role,
            subtask=subtask,
            origin=kwargs.get("origin", "delegate_subtask"),
            session_id=session_id,
            tenant_id=tenant_uuid,
        )
        return {"delegated_to": role, "subtask": subtask, "status": task.status.value, "task_id": task.task_id}

    registry.register(
        ToolSpec("delegate_subtask", "Queue a subtask for another personality on the shared task board.", _delegate, tags=["workflow"])
    )
    return registry
