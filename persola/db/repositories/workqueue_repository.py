"""Repositories for the async work queue — org chart, tasks, audit events.

Rows are returned as ORM models; orchestration stores hydrate them into
dataclasses. No orchestration imports live here (keeps layering clean).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AuditEventModel, AuditEventType, OrgNodeModel, WorkTaskModel, WorkTaskStatus
from .base import BaseRepository


def _ensure_utc(value: datetime | None) -> datetime | None:
	if value is None:
		return None
	if value.tzinfo is None:
		return value.replace(tzinfo=timezone.utc)
	return value


def _now() -> datetime:
	return datetime.now(timezone.utc)


class OrgNodeRepository(BaseRepository[OrgNodeModel]):
	def __init__(self, session: AsyncSession) -> None:
		super().__init__(session, OrgNodeModel)

	async def list_for_team(self, team_id: str) -> list[OrgNodeModel]:
		result = await self.session.execute(
			select(OrgNodeModel)
			.where(OrgNodeModel.team_id == team_id)
			.order_by(OrgNodeModel.role)
		)
		return list(result.scalars().all())

	async def get_node(self, team_id: str, role: str) -> OrgNodeModel | None:
		result = await self.session.execute(
			select(OrgNodeModel).where(
				OrgNodeModel.team_id == team_id,
				OrgNodeModel.role == role,
			)
		)
		return result.scalar_one_or_none()

	async def upsert(
		self,
		team_id: str,
		*,
		role: str,
		title: str,
		reports_to: Optional[str],
		email: Optional[str],
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
	def __init__(self, session: AsyncSession) -> None:
		super().__init__(session, WorkTaskModel)

	async def create_task(
		self,
		*,
		task_id: str,
		team_id: str,
		role: str,
		subtask: str,
		origin: str,
		status: str,
		parent_task_id: Optional[str] = None,
		session_id: Optional[str] = None,
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
		self.session.add(task)
		await self.session.flush()
		return task

	async def get_by_task_id(self, task_id: str) -> WorkTaskModel | None:
		result = await self.session.execute(
			select(WorkTaskModel).where(WorkTaskModel.task_id == task_id)
		)
		return result.scalar_one_or_none()

	async def list_for_team(self, team_id: str) -> list[WorkTaskModel]:
		result = await self.session.execute(
			select(WorkTaskModel)
			.where(WorkTaskModel.team_id == team_id)
			.order_by(WorkTaskModel.created_at)
		)
		return list(result.scalars().all())

	async def children(self, parent_task_id: str) -> list[WorkTaskModel]:
		result = await self.session.execute(
			select(WorkTaskModel)
			.where(WorkTaskModel.parent_task_id == parent_task_id)
			.order_by(WorkTaskModel.created_at)
		)
		return list(result.scalars().all())

	async def recover_stale(
		self, team_id: str, *, stale_after_seconds: int = 600
	) -> int:
		cutoff = _now() - timedelta(seconds=stale_after_seconds)
		result = await self.session.execute(
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
		return result.rowcount or 0

	async def claim_next(
		self, team_id: str, role: Optional[str]
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
		result: Optional[str] = None,
		error: Optional[str] = None,
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
	def __init__(self, session: AsyncSession) -> None:
		super().__init__(session, AuditEventModel)

	async def create_event(
		self,
		*,
		event_id: str,
		team_id: str,
		event_type: str,
		actor: str,
		summary: str,
		recipient: Optional[str] = None,
		session_id: Optional[str] = None,
		task_id: Optional[str] = None,
		detail: Optional[dict] = None,
		created_at: Optional[datetime] = None,
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
		self.session.add(event)
		await self.session.flush()
		return event

	async def timeline(
		self,
		team_id: str,
		*,
		session_id: Optional[str] = None,
		task_id: Optional[str] = None,
		limit: int = 200,
	) -> list[AuditEventModel]:
		filters: list = [AuditEventModel.team_id == team_id]
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
