from __future__ import annotations

from typing import Any
from uuid import UUID
import json
import os

from redis.asyncio import Redis


class PersonaCache:
    """Redis-backed cache for system prompts and sampling params."""

    TTL = 300  # 5 minutes

    def __init__(self, redis_url: str | None = None) -> None:
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://redis:6379/0")
        self._redis: Redis | None = None

    @property
    def client(self) -> Redis:
        if self._redis is None:
            self._redis = Redis.from_url(self.redis_url, decode_responses=True)
        return self._redis

    def _prompt_key(self, persona_id: UUID) -> str:
        return f"persola:persona:{persona_id}:system_prompt"

    def _sampling_key(self, persona_id: UUID) -> str:
        return f"persola:persona:{persona_id}:sampling"

    async def get_system_prompt(self, persona_id: UUID) -> str | None:
        try:
            return await self.client.get(self._prompt_key(persona_id))
        except Exception:
            return None

    async def set_system_prompt(self, persona_id: UUID, prompt: str) -> None:
        try:
            await self.client.set(self._prompt_key(persona_id), prompt, ex=self.TTL)
        except Exception:
            return None

    async def get_sampling(self, persona_id: UUID) -> dict[str, Any] | None:
        try:
            raw = await self.client.get(self._sampling_key(persona_id))
            if not raw:
                return None
            data = json.loads(raw)
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    async def set_sampling(self, persona_id: UUID, params: dict[str, Any]) -> None:
        try:
            await self.client.set(
                self._sampling_key(persona_id),
                json.dumps(params),
                ex=self.TTL,
            )
        except Exception:
            return None

    async def invalidate(self, persona_id: UUID) -> None:
        try:
            await self.client.delete(self._prompt_key(persona_id), self._sampling_key(persona_id))
        except Exception:
            return None
