"""Session-scoped memory tools for agent teams, namespaced per tenant."""

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
    """In-process memory store keyed by session and tenant."""

    def __init__(self) -> None:
        self._sessions: Dict[str, Dict[str, MemoryEntry]] = {}

    def _bucket(self, session_id: str, tenant_id: Optional[str] = None) -> Dict[str, MemoryEntry]:
        composite = f"{tenant_id}:{session_id}" if tenant_id else session_id
        if composite not in self._sessions:
            self._sessions[composite] = {}
        return self._sessions[composite]

    def store(
        self,
        session_id: str,
        key: str,
        value: Any,
        *,
        tenant_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        source_role: str = "system",
    ) -> None:
        self._bucket(session_id, tenant_id)[key] = MemoryEntry(
            key=key, value=value, tags=tags or [], source_role=source_role
        )

    def recall(
        self,
        session_id: str,
        key: str,
        *,
        tenant_id: Optional[str] = None,
    ) -> Optional[Any]:
        entry = self._bucket(session_id, tenant_id).get(key)
        return entry.value if entry else None

    def search(
        self,
        session_id: str,
        query: str,
        *,
        tenant_id: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        query_lower = query.lower()
        hits: List[Dict[str, Any]] = []
        for entry in self._bucket(session_id, tenant_id).values():
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

    def snapshot(self, session_id: str, *, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        return {k: v.value for k, v in self._bucket(session_id, tenant_id).items()}

    def clear_session(self, session_id: str, *, tenant_id: Optional[str] = None) -> None:
        composite = f"{tenant_id}:{session_id}" if tenant_id else session_id
        self._sessions.pop(composite, None)


# Shared process memory (API layer can swap for Redis later)
GLOBAL_MEMORY = MemoryStore()


def _tenant_suffix(tenant_id: Optional[str]) -> Optional[str]:
    return str(tenant_id) if tenant_id else None


def memory_store_tool(
    session_id: str,
    key: str,
    value: str,
    *,
    tenant_id: Optional[str] = None,
) -> Dict[str, Any]:
    GLOBAL_MEMORY.store(session_id, key, value, tenant_id=_tenant_suffix(tenant_id), tags=["tool:memory_store"])
    return {"stored": True, "key": key}


def memory_recall_tool(
    session_id: str,
    key: str,
    *,
    tenant_id: Optional[str] = None,
) -> Dict[str, Any]:
    value = GLOBAL_MEMORY.recall(session_id, key, tenant_id=_tenant_suffix(tenant_id))
    return {"key": key, "value": value, "found": value is not None}


def memory_search_tool(
    session_id: str,
    query: str,
    *,
    tenant_id: Optional[str] = None,
) -> Dict[str, Any]:
    return {"query": query, "results": GLOBAL_MEMORY.search(session_id, query, tenant_id=_tenant_suffix(tenant_id))}