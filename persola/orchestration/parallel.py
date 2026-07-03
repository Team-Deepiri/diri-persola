"""Parallel tool execution with concurrency limits and timeouts."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional


@dataclass
class ToolCallResult:
    name: str
    success: bool
    result: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    duration_ms: int = 0


class ParallelToolExecutor:
    def __init__(self, max_concurrency: int = 8, default_timeout_s: float = 30.0) -> None:
        self.max_concurrency = max_concurrency
        self.default_timeout_s = default_timeout_s
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def run_one(
        self,
        name: str,
        handler: Callable[..., Awaitable[Dict[str, Any]]],
        args: Dict[str, Any],
        *,
        timeout_s: Optional[float] = None,
    ) -> ToolCallResult:
        started = time.perf_counter()
        timeout = timeout_s or self.default_timeout_s
        async with self._semaphore:
            try:
                result = await asyncio.wait_for(handler(**args), timeout=timeout)
                return ToolCallResult(
                    name=name,
                    success=True,
                    result=result,
                    duration_ms=int((time.perf_counter() - started) * 1000),
                )
            except asyncio.TimeoutError:
                return ToolCallResult(
                    name=name,
                    success=False,
                    error=f"timeout after {timeout}s",
                    duration_ms=int((time.perf_counter() - started) * 1000),
                )
            except Exception as exc:
                return ToolCallResult(
                    name=name,
                    success=False,
                    error=str(exc),
                    duration_ms=int((time.perf_counter() - started) * 1000),
                )

    async def run_batch(
        self,
        registry: Any,
        calls: List[Dict[str, Any]],
    ) -> List[ToolCallResult]:
        tasks = []
        for call in calls:
            name = call["name"]
            args = call.get("args", {})
            spec = registry.get(name)
            if spec is None:
                tasks.append(
                    asyncio.create_task(
                        self._immediate_error(name, f"unknown tool: {name}")
                    )
                )
                continue
            tasks.append(asyncio.create_task(self.run_one(name, spec.handler, args)))
        return list(await asyncio.gather(*tasks))

    async def _immediate_error(self, name: str, error: str) -> ToolCallResult:
        return ToolCallResult(name=name, success=False, error=error)
