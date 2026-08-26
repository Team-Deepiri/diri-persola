"""Parallel tool execution with concurrency limits and timeouts."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCallResult:
    name: str
    success: bool
    result: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    duration_ms: int = 0


class ParallelToolExecutor:
    def __init__(self, max_concurrency: int = 8, default_timeout_s: float = 30.0) -> None:
        self.max_concurrency = max_concurrency
        self.default_timeout_s = default_timeout_s
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def run_one(
        self,
        name: str,
        handler: Callable[..., Awaitable[dict[str, Any]]],
        args: dict[str, Any],
        *,
        timeout_s: float | None = None,
        retries: int = 0,
        retry_delay_s: float = 1.0,
    ) -> ToolCallResult:
        started = time.perf_counter()
        timeout = timeout_s or self.default_timeout_s
        last_error: str | None = None
        async with self._semaphore:
            for attempt in range(1 + retries):
                try:
                    result = await asyncio.wait_for(handler(**args), timeout=timeout)
                    return ToolCallResult(
                        name=name,
                        success=True,
                        result=result,
                        duration_ms=int((time.perf_counter() - started) * 1000),
                    )
                except asyncio.TimeoutError:
                    last_error = f"timeout after {timeout}s"
                except Exception as exc:
                    last_error = str(exc)
                if attempt < retries:
                    await asyncio.sleep(retry_delay_s)
            return ToolCallResult(
                name=name,
                success=False,
                error=last_error,
                duration_ms=int((time.perf_counter() - started) * 1000),
            )

    async def run_batch(
        self,
        registry: Any,
        calls: list[dict[str, Any]],
    ) -> list[ToolCallResult]:
        """Run a batch; non-``parallel_safe`` tools are serialized."""
        results: list[ToolCallResult | None] = [None] * len(calls)
        parallel_tasks: list[asyncio.Task] = []
        parallel_idx: list[int] = []

        for i, call in enumerate(calls):
            name = call["name"]
            args = call.get("args", {})
            spec = registry.get(name)
            if spec is None:
                results[i] = ToolCallResult(name=name, success=False, error=f"unknown tool: {name}")
                continue
            if not getattr(spec, "parallel_safe", True):
                results[i] = await self.run_one(
                    name,
                    spec.handler,
                    args,
                    retries=getattr(spec, "retries", 0),
                    retry_delay_s=getattr(spec, "retry_delay_s", 1.0),
                )
            else:
                parallel_idx.append(i)
                parallel_tasks.append(
                    asyncio.create_task(
                        self.run_one(
                            name,
                            spec.handler,
                            args,
                            retries=getattr(spec, "retries", 0),
                            retry_delay_s=getattr(spec, "retry_delay_s", 1.0),
                        )
                    )
                )

        if parallel_tasks:
            parallel_results = await asyncio.gather(*parallel_tasks)
            for i, res in zip(parallel_idx, parallel_results):
                results[i] = res

        return [
            r if r is not None else ToolCallResult(name="unknown", success=False, error="missing")
            for r in results
        ]

    async def _immediate_error(self, name: str, error: str) -> ToolCallResult:
        return ToolCallResult(name=name, success=False, error=error)
