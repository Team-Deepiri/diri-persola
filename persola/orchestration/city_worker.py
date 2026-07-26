"""In-process city worker pool — queued tool runs with concurrency governance."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from .city_scale import DEFAULT_SCALE_CONFIG, GLOBAL_GOVERNOR, ScaleConfig, ConcurrencyGovernor


@dataclass
class CityWorkItem:
	id: str
	job_id: UUID
	family_id: UUID
	district: str
	calls: list[dict[str, Any]]
	agent_id: UUID | None = None
	created_at: float = field(default_factory=time.time)
	result: dict[str, Any] | None = None
	error: str | None = None
	status: str = "queued"  # queued | running | completed | failed


class CityWorkerPool:
	"""Asyncio queue + N workers executing city tool batches under the governor."""

	def __init__(
		self,
		config: ScaleConfig | None = None,
		governor: ConcurrencyGovernor | None = None,
	) -> None:
		self.config = config or DEFAULT_SCALE_CONFIG
		self.governor = governor or GLOBAL_GOVERNOR
		self._queue: asyncio.Queue[CityWorkItem | None] = asyncio.Queue(
			maxsize=self.config.queue_maxsize
		)
		self._workers: list[asyncio.Task] = []
		self._started = False
		self._items: dict[str, CityWorkItem] = {}
		self.completed = 0
		self.failed = 0
		self._lock = asyncio.Lock()

	@property
	def queue_depth(self) -> int:
		return self._queue.qsize()

	@property
	def busy_workers(self) -> int:
		return sum(1 for t in self._workers if not t.done() and self.governor.active_global >= 0)

	async def start(self) -> None:
		if self._started:
			return
		self._started = True
		for i in range(self.config.worker_count):
			self._workers.append(asyncio.create_task(self._worker_loop(i), name=f"city-worker-{i}"))

	async def stop(self) -> None:
		if not self._started:
			return
		for _ in self._workers:
			await self._queue.put(None)
		await asyncio.gather(*self._workers, return_exceptions=True)
		self._workers.clear()
		self._started = False

	async def enqueue(self, item: CityWorkItem) -> CityWorkItem:
		await self.start()
		self._items[item.id] = item
		await self._queue.put(item)
		try:
			from ..metrics import set_city_queue_depth

			set_city_queue_depth(self.queue_depth)
		except Exception:
			pass
		return item

	def get(self, work_id: str) -> CityWorkItem | None:
		return self._items.get(work_id)

	def snapshot(self) -> dict[str, Any]:
		return {
			"started": self._started,
			"worker_count": len(self._workers),
			"queue_depth": self.queue_depth,
			"completed": self.completed,
			"failed": self.failed,
			"tracked_items": len(self._items),
			"governor": self.governor.snapshot(),
		}

	async def _worker_loop(self, worker_id: int) -> None:
		from ..db.database import AsyncSessionLocal
		from ..metrics import (
			observe_city_job_duration,
			record_city_tool_run,
			set_city_queue_depth,
		)
		from ..services.city_service import CityService

		while True:
			item = await self._queue.get()
			try:
				if item is None:
					return
				item.status = "running"
				started = time.perf_counter()
				await self.governor.acquire(family_id=str(item.family_id), district=item.district)
				try:
					async with AsyncSessionLocal() as session:
						service = CityService(session)
						result = await service.execute_tool_calls(
							item.job_id,
							item.calls,
							agent_id=item.agent_id,
						)
						item.result = result
						item.status = "completed"
						self.completed += 1
						for tr in result.get("tool_results", []):
							record_city_tool_run(
								str(tr.get("name") or "unknown"),
								"ok" if tr.get("ok") else "error",
							)
				except Exception as exc:  # noqa: BLE001
					item.error = str(exc)
					item.status = "failed"
					self.failed += 1
					record_city_tool_run("batch", "failed")
				finally:
					self.governor.release(family_id=str(item.family_id), district=item.district)
					observe_city_job_duration(item.district, time.perf_counter() - started)
					set_city_queue_depth(self.queue_depth)
			finally:
				self._queue.task_done()


CITY_WORKER_POOL = CityWorkerPool()


async def enqueue_city_tools(
	*,
	job_id: UUID,
	family_id: UUID,
	district: str,
	calls: list[dict[str, Any]],
	agent_id: UUID | None = None,
) -> CityWorkItem:
	item = CityWorkItem(
		id=str(uuid4()),
		job_id=job_id,
		family_id=family_id,
		district=district or "build",
		calls=calls,
		agent_id=agent_id,
	)
	return await CITY_WORKER_POOL.enqueue(item)
