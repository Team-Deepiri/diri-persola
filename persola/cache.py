from __future__ import annotations

from typing import Any
from uuid import UUID
import json
import os
import random
import time

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


# ---------------------------------------------------------------------------
# Token-bucket rate limiter (Lua script, atomic Redis execution)
# ---------------------------------------------------------------------------

_TOKEN_BUCKET_LUA = """
local key          = KEYS[1]
local capacity     = tonumber(ARGV[1])   -- maximum burst size (tokens)
local refill_rate  = tonumber(ARGV[2])   -- tokens added per second
local now          = tonumber(ARGV[3])   -- current UNIX timestamp (float seconds)
local requested    = tonumber(ARGV[4])   -- tokens requested (usually 1)
local ttl          = tonumber(ARGV[5])   -- Redis key TTL in seconds

-- Load existing state (or bootstrap on first call)
local data        = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens      = tonumber(data[1]) or capacity
local last_refill = tonumber(data[2]) or now

-- Refill based on elapsed wall-clock time, capped at capacity
local elapsed  = math.max(0, now - last_refill)
local refilled = math.min(capacity, tokens + elapsed * refill_rate)

-- Consume tokens if available
local allowed  = 0
if refilled >= requested then
    refilled = refilled - requested
    allowed  = 1
end

-- Persist updated state and reset expiry
redis.call('HMSET', key, 'tokens', refilled, 'last_refill', now)
redis.call('EXPIRE', key, ttl)

-- Return {allowed (0|1), remaining (integer floor)}
return {allowed, math.floor(refilled)}
"""


class TokenBucketRateLimiter:
    """Redis-backed token-bucket rate limiter using an atomic Lua script.

    The Lua script executes as a single Redis command, so there is no race
    condition between read-compute-write even under concurrent requests.

    Args:
        capacity:    Maximum number of tokens (burst ceiling).
        refill_rate: Tokens replenished per second (sustain throughput).
        redis_url:   Redis connection URL; falls back to ``REDIS_URL`` env var.

    Example::

        limiter = TokenBucketRateLimiter(capacity=30, refill_rate=0.5)
        allowed, remaining = await limiter.consume("ip:127.0.0.1")
    """

    KEY_PREFIX = "persola:ratelimit:tb"

    def __init__(
        self,
        capacity: int = 30,
        refill_rate: float = 0.5,
        redis_url: str | None = None,
    ) -> None:
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        if refill_rate <= 0:
            raise ValueError("refill_rate must be > 0")
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://redis:6379/0")
        self._redis: Redis | None = None
        # TTL generous enough that the bucket persists across the window,
        # but expires if the key goes idle (2× the fill-to-full time).
        self._ttl: int = max(60, int(capacity / refill_rate * 2))

    @property
    def client(self) -> Redis:
        if self._redis is None:
            self._redis = Redis.from_url(self.redis_url, decode_responses=False)
        return self._redis

    def _key(self, identifier: str) -> str:
        return f"{self.KEY_PREFIX}:{identifier}"

    async def consume(
        self,
        identifier: str,
        tokens: int = 1,
    ) -> tuple[bool, int]:
        """Attempt to consume *tokens* from the bucket for *identifier*.

        Returns:
            A ``(allowed, remaining)`` tuple where *allowed* is ``True`` when
            the request is within the limit and *remaining* is the number of
            whole tokens left after the call.

        If Redis is unavailable the call fails open (returns ``True``) so a
        Redis outage does not take down the API entirely.
        """
        try:
            result = await self.client.eval(
                _TOKEN_BUCKET_LUA,
                1,
                self._key(identifier),
                self.capacity,
                self.refill_rate,
                time.time(),
                tokens,
                self._ttl,
            )
            allowed = int(result[0]) == 1
            remaining = int(result[1])
            return allowed, remaining
        except Exception:
            # Fail open: don't let a Redis hiccup block all requests.
            return True, self.capacity

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None

