"""Session-scoped memory tools for agent teams."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MemoryEntry:
    key: str
    value: Any
    tags: List[str] = field(default_factory=list)
    source_role: str = "system"


class MemoryStore:
    """In-process memory store keyed by session."""

    def __init__(self) -> None:
        self._sessions: Dict[str, Dict[str, MemoryEntry]] = {}

    def _bucket(self, session_id: str) -> Dict[str, MemoryEntry]:
        if session_id not in self._sessions:
            self._sessions[session_id] = {}
        return self._sessions[session_id]

    def store(self, session_id: str, key: str, value: Any, *, tags: Optional[List[str]] = None, source_role: str = "system") -> None:
        self._bucket(session_id)[key] = MemoryEntry(key=key, value=value, tags=tags or [], source_role=source_role)

    def recall(self, session_id: str, key: str) -> Optional[Any]:
        entry = self._bucket(session_id).get(key)
        return entry.value if entry else None

    def search(self, session_id: str, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        query_lower = query.lower()
        hits: List[Dict[str, Any]] = []
        for entry in self._bucket(session_id).values():
            haystack = f"{entry.key} {entry.value} {' '.join(entry.tags)}".lower()
            if query_lower in haystack:
                hits.append(
                    {
                        "key": entry.key,
                        "value": entry.value,
                        "tags": entry.tags,
                        "source_role": entry.source_role,
                    }
                )
        return hits[:limit]

    def snapshot(self, session_id: str) -> Dict[str, Any]:
        return {k: v.value for k, v in self._bucket(session_id).items()}

    def clear_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


# Shared process memory (API layer can swap for Redis later)
GLOBAL_MEMORY = MemoryStore()


def memory_store_tool(session_id: str, key: str, value: str) -> Dict[str, Any]:
    GLOBAL_MEMORY.store(session_id, key, value, tags=["tool:memory_store"])
    return {"stored": True, "key": key}


def memory_recall_tool(session_id: str, key: str) -> Dict[str, Any]:
    value = GLOBAL_MEMORY.recall(session_id, key)
    return {"key": key, "value": value, "found": value is not None}


def memory_search_tool(session_id: str, query: str) -> Dict[str, Any]:
    return {"query": query, "results": GLOBAL_MEMORY.search(session_id, query)}
