"""Redis-backed team memory with DB fallback."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from redis.asyncio import Redis


class RedisTeamMemory:
    KEY_PREFIX = "persola:team:memory"

    def __init__(self, redis_url: str | None = None) -> None:
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://redis:6379/0")
        self._redis: Redis | None = None

    @property
    def client(self) -> Redis:
        if self._redis is None:
            self._redis = Redis.from_url(self.redis_url, decode_responses=True)
        return self._redis

    def _hash_key(self, session_id: str) -> str:
        return f"{self.KEY_PREFIX}:{session_id}"

    async def store(
        self,
        session_id: str,
        key: str,
        value: Any,
        *,
        tags: Optional[List[str]] = None,
        source_role: str = "system",
    ) -> None:
        payload = json.dumps({"value": value, "tags": tags or [], "source_role": source_role})
        try:
            await self.client.hset(self._hash_key(session_id), key, payload)
            await self.client.expire(self._hash_key(session_id), 86400)
        except Exception:
            return None

    async def recall(self, session_id: str, key: str) -> Optional[Any]:
        try:
            raw = await self.client.hget(self._hash_key(session_id), key)
            if not raw:
                return None
            data = json.loads(raw)
            return data.get("value")
        except Exception:
            return None

    async def search(self, session_id: str, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        try:
            all_entries = await self.client.hgetall(self._hash_key(session_id))
        except Exception:
            return []
        query_lower = query.lower()
        hits: List[Dict[str, Any]] = []
        for key, raw in all_entries.items():
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            haystack = f"{key} {data.get('value', '')} {' '.join(data.get('tags', []))}".lower()
            if query_lower in haystack:
                hits.append({"key": key, **data})
        return hits[:limit]

    async def snapshot(self, session_id: str) -> Dict[str, Any]:
        try:
            all_entries = await self.client.hgetall(self._hash_key(session_id))
        except Exception:
            return {}
        out: Dict[str, Any] = {}
        for key, raw in all_entries.items():
            try:
                out[key] = json.loads(raw).get("value")
            except json.JSONDecodeError:
                continue
        return out

    async def clear(self, session_id: str) -> None:
        try:
            await self.client.delete(self._hash_key(session_id))
        except Exception:
            return None


REDIS_TEAM_MEMORY = RedisTeamMemory()
