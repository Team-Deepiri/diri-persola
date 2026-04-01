from __future__ import annotations

from typing import Any
from uuid import UUID
import json
import os
import random

from redis.asyncio import Redis


class PersonaCache:
    """Redis-backed cache for derived persona artifacts.

    Uses a versioned cache-aside pattern so invalidation is race-safe even when
    an older in-flight request finishes after a persona update.
    """

    TTL = 300
    TTL_JITTER = 60
    KEY_PREFIX = "persola:persona"

    def __init__(self, redis_url: str | None = None) -> None:
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://redis:6379/0")
        self._redis: Redis | None = None

    @property
    def client(self) -> Redis:
        if self._redis is None:
            self._redis = Redis.from_url(self.redis_url, decode_responses=True)
        return self._redis

    def _generation_key(self, persona_id: UUID) -> str:
        return f"{self.KEY_PREFIX}:{persona_id}:generation"

    def _entry_key(self, persona_id: UUID, generation: int) -> str:
        return f"{self.KEY_PREFIX}:{persona_id}:entry:{generation}"

    def _ttl(self) -> int:
        return self.TTL + random.randint(0, self.TTL_JITTER)

    async def _get_generation(self, persona_id: UUID) -> int:
        raw = await self.client.get(self._generation_key(persona_id))
        if raw is None:
            return 0
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 0

    async def _get_entry(self, persona_id: UUID) -> dict[str, Any] | None:
        try:
            generation = await self._get_generation(persona_id)
            return await self._get_entry_for_generation(persona_id, generation)
        except Exception:
            return None

    async def _get_entry_for_generation(self, persona_id: UUID, generation: int) -> dict[str, Any] | None:
        raw = await self.client.get(self._entry_key(persona_id, generation))
        if not raw:
            return None
        payload = json.loads(raw)
        return payload if isinstance(payload, dict) else None

    async def _set_fields(self, persona_id: UUID, fields: dict[str, Any]) -> None:
        try:
            generation = await self._get_generation(persona_id)
            entry_key = self._entry_key(persona_id, generation)
            current = await self._get_entry_for_generation(persona_id, generation) or {}
            current.update(fields)
            await self.client.set(entry_key, json.dumps(current), ex=self._ttl())
        except Exception:
            return None

    async def get_system_prompt(self, persona_id: UUID) -> str | None:
        payload = await self._get_entry(persona_id)
        prompt = payload.get("system_prompt") if payload else None
        return prompt if isinstance(prompt, str) and prompt else None

    async def set_system_prompt(self, persona_id: UUID, prompt: str) -> None:
        await self._set_fields(persona_id, {"system_prompt": prompt})

    async def get_sampling(self, persona_id: UUID) -> dict[str, Any] | None:
        payload = await self._get_entry(persona_id)
        sampling = payload.get("sampling") if payload else None
        return sampling if isinstance(sampling, dict) else None

    async def set_sampling(self, persona_id: UUID, params: dict[str, Any]) -> None:
        await self._set_fields(persona_id, {"sampling": params})

    async def invalidate(self, persona_id: UUID) -> None:
        try:
            generation_key = self._generation_key(persona_id)
            current_generation = await self._get_generation(persona_id)
            next_generation = current_generation + 1
            entry_keys = [self._entry_key(persona_id, current_generation), self._entry_key(persona_id, next_generation)]
            async with self.client.pipeline(transaction=False) as pipe:
                pipe.set(generation_key, next_generation)
                pipe.delete(*entry_keys)
                await pipe.execute()
        except Exception:
            return None
