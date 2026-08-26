"""Tool registry with parallel execution for agent teams."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

ToolHandler = Callable[..., Awaitable[dict[str, Any]]]


@dataclass
class ToolSpec:
    name: str
    description: str
    handler: ToolHandler
    parallel_safe: bool = True
    tags: list[str] = field(default_factory=list)
    input_schema: dict[str, Any] | None = None  # JSON Schema for kwargs validation
    retries: int = 0  # retry count for transient failures
    retry_delay_s: float = 1.0  # delay between retries


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
                "retries": t.retries,
            }
            for t in self._tools.values()
        ]

    @staticmethod
    def _validate_args(spec: ToolSpec, kwargs: dict[str, Any]) -> str | None:
        """Validate kwargs against spec.input_schema. Returns error message or None."""
        schema = spec.input_schema
        if schema is None:
            return None
        required = schema.get("required", [])
        properties = schema.get("properties", {})
        for key in required:
            if key not in kwargs:
                return f"missing required argument: {key}"
        for key, value in kwargs.items():
            if key in properties:
                expected_type = properties[key].get("type")
                if expected_type == "string" and not isinstance(value, str):
                    return f"argument '{key}' must be a string"
                elif expected_type == "number" and not isinstance(value, (int, float)):
                    return f"argument '{key}' must be a number"
                elif expected_type == "integer" and not isinstance(value, int):
                    return f"argument '{key}' must be an integer"
                elif expected_type == "boolean" and not isinstance(value, bool):
                    return f"argument '{key}' must be a boolean"
                elif expected_type == "array" and not isinstance(value, list):
                    return f"argument '{key}' must be an array"
                elif expected_type == "object" and not isinstance(value, dict):
                    return f"argument '{key}' must be an object"
        return None

    async def run(self, name: str, **kwargs: Any) -> dict[str, Any]:
        spec = self._tools.get(name)
        if spec is None:
            return {"error": f"Unknown tool: {name}"}
        validation_error = self._validate_args(spec, kwargs)
        if validation_error:
            return {"error": "invalid_args", "details": validation_error}
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
            validation_error = self._validate_args(spec, args)
            if validation_error:
                return {"name": name, "error": "invalid_args", "details": validation_error}
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


def build_default_registry(session_id: str) -> ToolRegistry:
    from .memory import memory_recall_tool, memory_search_tool, memory_store_tool

    registry = ToolRegistry()

    async def _store(**kwargs: Any) -> dict[str, Any]:
        return memory_store_tool(session_id, kwargs["key"], kwargs["value"])

    async def _recall(**kwargs: Any) -> dict[str, Any]:
        return memory_recall_tool(session_id, kwargs["key"])

    async def _search(**kwargs: Any) -> dict[str, Any]:
        return memory_search_tool(session_id, kwargs["query"])

    async def _echo(**kwargs: Any) -> dict[str, Any]:
        return {"echo": kwargs.get("text", "")}

    registry.register(
        ToolSpec(
            "memory_store", "Persist a key/value in team session memory.", _store, tags=["memory"]
        )
    )
    registry.register(
        ToolSpec(
            "memory_recall", "Recall a value from team session memory.", _recall, tags=["memory"]
        )
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
        task = GLOBAL_TASK_QUEUE.enqueue(
            team_id=kwargs.get("team_id", "default"),
            role=role,
            subtask=subtask,
            origin=kwargs.get("origin", "delegate_subtask"),
            session_id=session_id,
        )
        return {
            "delegated_to": role,
            "subtask": subtask,
            "status": task.status.value,
            "task_id": task.task_id,
        }

    registry.register(
        ToolSpec(
            "delegate_subtask",
            "Queue a subtask for another personality on the shared task board.",
            _delegate,
            tags=["workflow"],
        )
    )
    return registry
