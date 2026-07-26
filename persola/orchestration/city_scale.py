"""City scale controls — concurrency, model tiers, district sharding."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ModelTier:
	"""Cheaper models for children; stronger for parent/coordinator."""

	parent: str = field(
		default_factory=lambda: os.getenv("PERSOLA_CITY_PARENT_MODEL", "llama3:70b")
	)
	child: str = field(
		default_factory=lambda: os.getenv("PERSOLA_CITY_CHILD_MODEL", "llama3:8b")
	)

	def for_role(self, role_in_family: str, role_label: str | None = None) -> str:
		if role_in_family == "parent" or (role_label or "") == "coordinator":
			return self.parent
		return self.child


@dataclass
class ScaleConfig:
	max_global_concurrent: int = int(os.getenv("PERSOLA_CITY_MAX_GLOBAL", "32"))
	max_per_family: int = int(os.getenv("PERSOLA_CITY_MAX_PER_FAMILY", "8"))
	max_per_district: int = int(os.getenv("PERSOLA_CITY_MAX_PER_DISTRICT", "16"))
	max_per_job: int = int(os.getenv("PERSOLA_CITY_MAX_PER_JOB", "4"))
	worker_count: int = int(os.getenv("PERSOLA_CITY_WORKERS", "4"))
	queue_maxsize: int = int(os.getenv("PERSOLA_CITY_QUEUE_MAX", "256"))
	model_tiers: ModelTier = field(default_factory=ModelTier)

	# Documented path-to-100 targets
	target_agents: int = 100
	probe_families: int = 5
	probe_agents_per_family: int = 10  # 5 × 10 = 50 sustained probe


DISTRICTS: tuple[str, ...] = ("build", "viz", "research", "ops")


def shard_for_district(district: str) -> str:
	"""Map a city district onto a worker shard key."""
	d = (district or "build").lower().strip()
	if d not in DISTRICTS:
		d = "build"
	return f"district:{d}"


class ConcurrencyGovernor:
	"""Fair concurrency limits: global + per-family + per-district + per-job."""

	def __init__(self, config: ScaleConfig | None = None) -> None:
		self.config = config or ScaleConfig()
		self._global = asyncio.Semaphore(self.config.max_global_concurrent)
		self._family: dict[str, asyncio.Semaphore] = {}
		self._district: dict[str, asyncio.Semaphore] = {}
		self._job: dict[str, asyncio.Semaphore] = {}
		self._lock = asyncio.Lock()
		self.active_global = 0
		self.active_by_family: dict[str, int] = {}
		self.active_by_district: dict[str, int] = {}
		self.active_by_job: dict[str, int] = {}

	async def _family_sem(self, family_id: str) -> asyncio.Semaphore:
		async with self._lock:
			if family_id not in self._family:
				self._family[family_id] = asyncio.Semaphore(self.config.max_per_family)
			return self._family[family_id]

	async def _district_sem(self, district: str) -> asyncio.Semaphore:
		key = shard_for_district(district)
		async with self._lock:
			if key not in self._district:
				self._district[key] = asyncio.Semaphore(self.config.max_per_district)
			return self._district[key]

	async def _job_sem(self, job_id: str) -> asyncio.Semaphore:
		async with self._lock:
			if job_id not in self._job:
				self._job[job_id] = asyncio.Semaphore(self.config.max_per_job)
			return self._job[job_id]

	async def acquire(self, *, family_id: str, district: str = "build", job_id: str | None = None) -> None:
		fam = await self._family_sem(family_id)
		dist = await self._district_sem(district)
		job = await self._job_sem(job_id) if job_id else None
		await self._global.acquire()
		try:
			await fam.acquire()
		except Exception:
			self._global.release()
			raise
		try:
			await dist.acquire()
		except Exception:
			fam.release()
			self._global.release()
			raise
		if job is not None:
			try:
				await job.acquire()
			except Exception:
				dist.release()
				fam.release()
				self._global.release()
				raise
		self.active_global += 1
		self.active_by_family[family_id] = self.active_by_family.get(family_id, 0) + 1
		dk = shard_for_district(district)
		self.active_by_district[dk] = self.active_by_district.get(dk, 0) + 1
		if job_id:
			self.active_by_job[job_id] = self.active_by_job.get(job_id, 0) + 1

	def release(self, *, family_id: str, district: str = "build", job_id: str | None = None) -> None:
		dk = shard_for_district(district)
		if job_id:
			js = self._job.get(job_id)
			if js is not None:
				js.release()
			if job_id in self.active_by_job:
				self.active_by_job[job_id] = max(0, self.active_by_job[job_id] - 1)
		dist = self._district.get(dk)
		fam = self._family.get(family_id)
		if dist is not None:
			dist.release()
		if fam is not None:
			fam.release()
		self._global.release()
		self.active_global = max(0, self.active_global - 1)
		if family_id in self.active_by_family:
			self.active_by_family[family_id] = max(0, self.active_by_family[family_id] - 1)
		if dk in self.active_by_district:
			self.active_by_district[dk] = max(0, self.active_by_district[dk] - 1)

	def snapshot(self) -> dict[str, Any]:
		return {
			"config": {
				"max_global_concurrent": self.config.max_global_concurrent,
				"max_per_family": self.config.max_per_family,
				"max_per_district": self.config.max_per_district,
				"max_per_job": self.config.max_per_job,
				"worker_count": self.config.worker_count,
				"parent_model": self.config.model_tiers.parent,
				"child_model": self.config.model_tiers.child,
				"target_agents": self.config.target_agents,
			},
			"active_global": self.active_global,
			"active_by_family": dict(self.active_by_family),
			"active_by_district": dict(self.active_by_district),
			"active_by_job": dict(self.active_by_job),
			"shards": [shard_for_district(d) for d in DISTRICTS],
		}


# Process-wide defaults used by workers / APIs
DEFAULT_SCALE_CONFIG = ScaleConfig()
GLOBAL_GOVERNOR = ConcurrencyGovernor(DEFAULT_SCALE_CONFIG)
