"""Repositories for the async work queue — org chart, tasks, audit events.

Rows are returned as ORM models; orchestration stores hydrate them into
dataclasses. No orchestration imports live here (keeps layering clean).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AuditEventModel, OrgNodeModel, WorkTaskModel, WorkTaskStatus
from .base import BaseRepository


def _now() -> datetime:
	from ...utils.time import utcnow

	return utcnow()


class OrgNodeRepository(BaseRepository[OrgNodeModel]):
	def __init__(self, session: AsyncSession, tenant_id: UUID | None = None) -> None:
		super().__init__(session, OrgNodeModel, tenant_id=tenant_id)

	def _scoped(self, query):
		return self._tenant_filter(query)

	async def list_for_team(self, team_id: str) -> list[OrgNodeModel]:
		result = await self.session.execute(
			self._scoped(
				select(OrgNodeModel)
				.where(OrgNodeModel.team_id == team_id)
				.order_by(OrgNodeModel.role)
			)
		)
		return list(result.scalars().all())

	async def get_node(self, team_id: str, role: str) -> OrgNodeModel | None:
		result = await self.session.execute(
			self._scoped(
				select(OrgNodeModel).where(
					OrgNodeModel.team_id == team_id,
					OrgNodeModel.role == role,
				)
			)
		)
		return result.scalar_one_or_none()

	async def upsert(
		self,
		team_id: str,
		*,
		role: str,
		title: str,
		reports_to: str | None,
		email: str | None,
		active: bool = True,
	) -> OrgNodeModel:
		node = await self.get_node(team_id, role)
		if node is None:
			node = OrgNodeModel(
				team_id=team_id,
				role=role,
				title=title,
				reports_to=reports_to,
				email=email,
				active=active,
			)
			if self._is_tenant_scoped:
				node.tenant_id = self.tenant_id
			self.session.add(node)
			await self.session.flush()
		else:
			node.title = title
			node.reports_to = reports_to
			node.email = email
			node.active = active
			await self.session.flush()
		return node

	async def deactivate(self, team_id: str, role: str) -> None:
		node = await self.get_node(team_id, role)
		if node is not None:
			node.active = False
			await self.session.flush()


class WorkTaskRepository(BaseRepository[WorkTaskModel]):
	def __init__(self, session: AsyncSession, tenant_id: UUID | None = None) -> None:
		super().__init__(session, WorkTaskModel, tenant_id=tenant_id)

	def _scoped(self, query):
		return self._tenant_filter(query)

	async def create_task(
		self,
		*,
		task_id: str,
		team_id: str,
		role: str,
		subtask: str,
		origin: str,
		status: str,
		parent_task_id: str | None = None,
		session_id: str | None = None,
	) -> WorkTaskModel:
		task = WorkTaskModel(
			task_id=task_id,
			team_id=team_id,
			role=role,
			subtask=subtask,
			origin=origin,
			status=status,
			parent_task_id=parent_task_id,
			session_id=session_id,
		)
		if self._is_tenant_scoped:
			task.tenant_id = self.tenant_id
		self.session.add(task)
		await self.session.flush()
		return task

	async def get_by_task_id(self, task_id: str) -> WorkTaskModel | None:
		result = await self.session.execute(
			self._scoped(select(WorkTaskModel).where(WorkTaskModel.task_id == task_id))
		)
		return result.scalar_one_or_none()

	async def list_for_team(self, team_id: str) -> list[WorkTaskModel]:
		result = await self.session.execute(
			self._scoped(
				select(WorkTaskModel)
				.where(WorkTaskModel.team_id == team_id)
				.order_by(WorkTaskModel.created_at)
			)
		)
		return list(result.scalars().all())

	async def children(self, parent_task_id: str) -> list[WorkTaskModel]:
		result = await self.session.execute(
			self._scoped(
				select(WorkTaskModel)
				.where(WorkTaskModel.parent_task_id == parent_task_id)
				.order_by(WorkTaskModel.created_at)
			)
		)
		return list(result.scalars().all())

	async def recover_stale(
		self, team_id: str, *, stale_after_seconds: int = 600
	) -> int:
		cutoff = _now() - timedelta(seconds=stale_after_seconds)
		stmt = (
			update(WorkTaskModel)
			.where(
				WorkTaskModel.team_id == team_id,
				WorkTaskModel.status.in_(
					[WorkTaskStatus.CLAIMED.value, WorkTaskStatus.IN_PROGRESS.value]
				),
				or_(WorkTaskModel.claimed_at.is_(None), WorkTaskModel.claimed_at < cutoff),
			)
			.values(status=WorkTaskStatus.QUEUED.value, error="re-queued: stale claim")
		)
		if self._is_tenant_scoped:
			stmt = stmt.where(WorkTaskModel.tenant_id == self.tenant_id)
		result = await self.session.execute(stmt)
		return result.rowcount or 0

	async def claim_next(
		self, team_id: str, role: str | None
	) -> WorkTaskModel | None:
		await self.recover_stale(team_id)
		stmt = (
			select(WorkTaskModel)
			.where(
				WorkTaskModel.team_id == team_id,
				WorkTaskModel.status == WorkTaskStatus.QUEUED.value,
			)
			.order_by(WorkTaskModel.created_at)
		)
		if self._is_tenant_scoped:
			stmt = stmt.where(WorkTaskModel.tenant_id == self.tenant_id)
		if role is not None:
			stmt = stmt.where(WorkTaskModel.role == role)
		if self.session.get_bind().dialect.name != "sqlite":
			stmt = stmt.with_for_update(skip_locked=True)
		result = await self.session.execute(stmt)
		row = result.scalars().first()
		if row is None:
			return None
		row.status = WorkTaskStatus.CLAIMED.value
		row.claimed_at = _now()
		await self.session.flush()
		return row

	async def update_status(
		self,
		task_id: str,
		status: str,
		*,
		result: str | None = None,
		error: str | None = None,
		mark_completed: bool = False,
	) -> WorkTaskModel | None:
		row = await self.get_by_task_id(task_id)
		if row is None:
			return None
		row.status = status
		if result is not None:
			row.result = result
		if error is not None:
			row.error = error
		if mark_completed:
			row.completed_at = _now()
		await self.session.flush()
		return row


class AuditEventRepository(BaseRepository[AuditEventModel]):
	def __init__(self, session: AsyncSession, tenant_id: UUID | None = None) -> None:
		super().__init__(session, AuditEventModel, tenant_id=tenant_id)

	def _scoped(self, query):
		return self._tenant_filter(query)

	async def create_event(
		self,
		*,
		event_id: str,
		team_id: str,
		event_type: str,
		actor: str,
		summary: str,
		recipient: str | None = None,
		session_id: str | None = None,
		task_id: str | None = None,
		detail: dict | None = None,
		created_at: datetime | None = None,
	) -> AuditEventModel:
		event = AuditEventModel(
			event_id=event_id,
			team_id=team_id,
			event_type=event_type,
			actor=actor,
			summary=summary,
			recipient=recipient,
			session_id=session_id,
			task_id=task_id,
			detail=dict(detail or {}),
			created_at=created_at or _now(),
		)
		if self._is_tenant_scoped:
			event.tenant_id = self.tenant_id
		self.session.add(event)
		await self.session.flush()
		return event

	async def timeline(
		self,
		team_id: str,
		*,
		session_id: str | None = None,
		task_id: str | None = None,
		limit: int = 200,
	) -> list[AuditEventModel]:
		filters: list = [AuditEventModel.team_id == team_id]
		if self._is_tenant_scoped:
			filters.append(AuditEventModel.tenant_id == self.tenant_id)
		if session_id is not None:
			filters.append(AuditEventModel.session_id == session_id)
		if task_id is not None:
			filters.append(AuditEventModel.task_id == task_id)
		result = await self.session.execute(
			select(AuditEventModel)
			.where(and_(*filters))
			.order_by(AuditEventModel.created_at.desc())
			.limit(limit)
		)
		rows = list(result.scalars().all())
		rows.reverse()
		return rows
