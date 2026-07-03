"""Tool registry with parallel execution for agent teams."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional


ToolHandler = Callable[..., Awaitable[Dict[str, Any]]]


@dataclass
class ToolSpec:
    name: str
    description: str
    handler: ToolHandler
    parallel_safe: bool = True
    tags: List[str] = field(default_factory=list)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def get(self, name: str) -> Optional[ToolSpec]:
        return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "parallel_safe": t.parallel_safe,
                "tags": t.tags,
            }
            for t in self._tools.values()
        ]

    async def run(self, name: str, **kwargs: Any) -> Dict[str, Any]:
        spec = self._tools.get(name)
        if spec is None:
            return {"error": f"Unknown tool: {name}"}
        return await spec.handler(**kwargs)

    async def run_parallel(self, calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Execute multiple tool calls concurrently when marked parallel_safe."""

        async def _one(call: Dict[str, Any]) -> Dict[str, Any]:
            name = call["name"]
            args = call.get("args", {})
            spec = self._tools.get(name)
            if spec is None:
                return {"name": name, "error": "unknown_tool"}
            if not spec.parallel_safe:
                result = await spec.handler(**args)
                return {"name": name, "result": result}
            result = await spec.handler(**args)
            return {"name": name, "result": result}

        return list(await asyncio.gather(*[_one(c) for c in calls]))


def build_default_registry(session_id: str) -> ToolRegistry:
    from .memory import memory_recall_tool, memory_search_tool, memory_store_tool

    registry = ToolRegistry()

    async def _store(**kwargs: Any) -> Dict[str, Any]:
        return memory_store_tool(session_id, kwargs["key"], kwargs["value"])

    async def _recall(**kwargs: Any) -> Dict[str, Any]:
        return memory_recall_tool(session_id, kwargs["key"])

    async def _search(**kwargs: Any) -> Dict[str, Any]:
        return memory_search_tool(session_id, kwargs["query"])

    async def _echo(**kwargs: Any) -> Dict[str, Any]:
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
    return registry
