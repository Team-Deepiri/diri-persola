"""Load agent tools from DB and register built-in orchestration tools."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.repositories.agent_tool_repository import AgentToolRepository
from .memory import GLOBAL_MEMORY, memory_recall_tool, memory_search_tool, memory_store_tool
from .parallel import ParallelToolExecutor
from .redis_memory import REDIS_TEAM_MEMORY
from .tools import ToolRegistry, ToolSpec


async def build_team_registry(
    session_id: str,
    *,
    db: Optional[AsyncSession] = None,
    agent_id: Optional[UUID] = None,
) -> ToolRegistry:
    registry = ToolRegistry()
    executor = ParallelToolExecutor()

    async def _store(**kwargs: Any) -> Dict[str, Any]:
        key, value = kwargs["key"], kwargs["value"]
        await REDIS_TEAM_MEMORY.store(session_id, key, value, source_role=kwargs.get("source_role", "tool"))
        memory_store_tool(session_id, key, str(value))
        return {"stored": True, "key": key}

    async def _recall(**kwargs: Any) -> Dict[str, Any]:
        key = kwargs["key"]
        redis_val = await REDIS_TEAM_MEMORY.recall(session_id, key)
        if redis_val is not None:
            return {"key": key, "value": redis_val, "found": True, "source": "redis"}
        return memory_recall_tool(session_id, key)

    async def _search(**kwargs: Any) -> Dict[str, Any]:
        query = kwargs["query"]
        redis_hits = await REDIS_TEAM_MEMORY.search(session_id, query)
        if redis_hits:
            return {"query": query, "results": redis_hits, "source": "redis"}
        return memory_search_tool(session_id, query)

    async def _persona_blend_preview(**kwargs: Any) -> Dict[str, Any]:
        from ..engine import PersonaEngine
        from ..models import PersonaProfile

        profiles = kwargs.get("profiles", [])
        weights = kwargs.get("weights", [])
        if len(profiles) < 2:
            return {"error": "need at least 2 persona knob dicts"}
        engine = PersonaEngine()
        persona_objs = [PersonaProfile(name=f"P{i}", **p) for i, p in enumerate(profiles)]
        blended = engine.blend_multiple(persona_objs, weights)
        return {"name": blended.name, "knobs": blended.get_knobs()}

    async def _cyrex_status(**kwargs: Any) -> Dict[str, Any]:
        from ..integrations.cyrex import CyrexClient

        client = CyrexClient()
        if not client.is_configured:
            return {"available": False}
        available = await client.is_available()
        return {"available": available, "configured": True}

    async def _delegate_subtask(**kwargs: Any) -> Dict[str, Any]:
        return {
            "delegated_to": kwargs.get("role", "executor"),
            "subtask": kwargs.get("subtask", ""),
            "status": "queued",
        }

    registry.register(ToolSpec("memory_store", "Persist key/value in team memory (Redis + local).", _store, tags=["memory"]))
    registry.register(ToolSpec("memory_recall", "Recall from team memory.", _recall, tags=["memory"]))
    registry.register(ToolSpec("memory_search", "Search team memory.", _search, tags=["memory"]))
    registry.register(ToolSpec("persona_blend_preview", "Blend persona knob profiles.", _persona_blend_preview, tags=["persona"]))
    registry.register(ToolSpec("cyrex_status", "Check Cyrex runtime connectivity.", _cyrex_status, tags=["platform"]))
    registry.register(ToolSpec("delegate_subtask", "Queue a subtask for another personality.", _delegate_subtask, tags=["workflow"]))

    if db is not None and agent_id is not None:
        tool_repo = AgentToolRepository(db)

        def _make_agent_tool(name: str, cfg: dict) -> Callable[..., Awaitable[Dict[str, Any]]]:
            async def _agent_tool(**kwargs: Any) -> Dict[str, Any]:
                return {"tool": name, "config": cfg, "input": kwargs, "status": "simulated"}

            return _agent_tool

        for tool_row in await tool_repo.list_by_agent(agent_id):
            if not tool_row.enabled:
                continue
            registry.register(
                ToolSpec(
                    f"agent_{tool_row.name}",
                    tool_row.description or f"Agent tool {tool_row.name}",
                    _make_agent_tool(tool_row.name, tool_row.tool_config),
                    tags=["agent", "db"],
                )
            )

    registry._executor = executor  # type: ignore[attr-defined]
    return registry
