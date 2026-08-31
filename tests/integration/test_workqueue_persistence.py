"""Workqueue persistence — org chart, task board, audit trail, daemon tick.

The global stores are pointed at a fresh in-memory DB by the autouse
``workqueue_store_db`` fixture, so every test here exercises real DB
read/write round-trips through self-opened sessions.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from persola.db.models import CityEventModel
from persola.db.repositories.workqueue_repository import WorkTaskRepository
from persola.orchestration.audit_log import AuditEventType, GLOBAL_AUDIT_LOG
from persola.orchestration.daemon import TaskQueueWorker
from persola.orchestration.org_chart import GLOBAL_ORG_CHART, OrgNode
from persola.orchestration.task_queue import GLOBAL_TASK_QUEUE, TaskStatus

pytestmark = pytest.mark.anyio


class _StubResult:
	def __init__(self, response: str) -> None:
		self.response = response


class _StubOrchestrator:
	"""Minimal stand-in for TeamOrchestrator — only ``run`` is exercised."""

	def __init__(self, response: str = "team result") -> None:
		self._response = response

	async def run(self, task: str, session=None):
		return _StubResult(self._response)


class TestTaskBoard:
	async def test_enqueue_claim_complete_persists(self):
		first = await GLOBAL_TASK_QUEUE.enqueue(
			team_id="default", role="analyst", subtask="analyze x", session_id="sess-1"
		)
		assert first.status == TaskStatus.QUEUED

		claimed = await GLOBAL_TASK_QUEUE.claim_next(team_id="default", role="analyst")
		assert claimed is not None
		assert claimed.status == TaskStatus.CLAIMED
		assert claimed.claimed_at is not None

		in_progress = await GLOBAL_TASK_QUEUE.mark_in_progress(claimed.task_id)
		assert in_progress.status == TaskStatus.IN_PROGRESS

		done = await GLOBAL_TASK_QUEUE.complete(claimed.task_id, "result!")
		assert done.status == TaskStatus.DONE
		assert done.completed_at is not None

		reloaded = await GLOBAL_TASK_QUEUE.get(first.task_id)
		assert reloaded.status == TaskStatus.DONE
		assert reloaded.result == "result!"
		assert reloaded.session_id == "sess-1"
		assert reloaded.role == "analyst"

	async def test_claim_respects_role(self):
		await GLOBAL_TASK_QUEUE.enqueue(team_id="default", role="analyst", subtask="a")
		await GLOBAL_TASK_QUEUE.enqueue(team_id="default", role="executor", subtask="b")
		claimed = await GLOBAL_TASK_QUEUE.claim_next(team_id="default", role="executor")
		assert claimed is not None
		assert claimed.role == "executor"
		assert claimed.subtask == "b"
		assert await GLOBAL_TASK_QUEUE.claim_next(team_id="default", role="executor") is None

	async def test_fail_records_error(self):
		task = await GLOBAL_TASK_QUEUE.enqueue(team_id="default", role="analyst", subtask="x")
		await GLOBAL_TASK_QUEUE.claim_next(team_id="default")
		failed = await GLOBAL_TASK_QUEUE.fail(task.task_id, "boom")
		assert failed.status == TaskStatus.FAILED
		assert failed.error == "boom"
		assert failed.completed_at is not None

	async def test_board_columns(self):
		await GLOBAL_TASK_QUEUE.enqueue(team_id="default", role="analyst", subtask="queued one")
		task = await GLOBAL_TASK_QUEUE.enqueue(team_id="default", role="executor", subtask="queued two")
		claimed = await GLOBAL_TASK_QUEUE.claim_next(team_id="default")
		await GLOBAL_TASK_QUEUE.complete(claimed.task_id, "done!")

		board = await GLOBAL_TASK_QUEUE.board("default")
		assert {c for c in board} == {s.value for s in TaskStatus}
		assert len(board["queued"]) == 1
		assert len(board["claimed"]) == 0
		assert board["done"][0]["task_id"] == claimed.task_id
		assert task.task_id in {t["task_id"] for t in board["queued"]}

	async def test_stale_claim_is_recovered(self):
		task = await GLOBAL_TASK_QUEUE.enqueue(team_id="default", role="analyst", subtask="x")
		claimed = await GLOBAL_TASK_QUEUE.claim_next(team_id="default")
		assert claimed is not None and claimed.status == TaskStatus.CLAIMED

		async with GLOBAL_TASK_QUEUE._open_session() as s:
			repo = WorkTaskRepository(s)
			row = await repo.get_by_task_id(task.task_id)
			row.status = "in_progress"
			row.claimed_at = datetime.now(timezone.utc) - timedelta(hours=1)
			await s.commit()

		reclaimed = await GLOBAL_TASK_QUEUE.claim_next(team_id="default")
		assert reclaimed is not None
		assert reclaimed.task_id == task.task_id
		assert reclaimed.status == TaskStatus.CLAIMED


class TestOrgChartPersistence:
	async def test_seeds_defaults_and_persists_custom_nodes(self):
		chart = await GLOBAL_ORG_CHART.to_dict("default")
		assert chart["team_id"] == "default"
		assert chart["top"] is not None
		assert any(n["role"] == chart["top"] for n in chart["nodes"])
		assert len(chart["nodes"]) >= 4

		await GLOBAL_ORG_CHART.upsert_node(
			"default",
			OrgNode(role="researcher", title="Senior Researcher", reports_to="coordinator"),
		)
		await GLOBAL_ORG_CHART.deactivate("default", "analyst")

		reloaded = await GLOBAL_ORG_CHART.to_dict("default")
		researcher = next(n for n in reloaded["nodes"] if n["role"] == "researcher")
		assert researcher["title"] == "Senior Researcher"
		analyst = next(n for n in reloaded["nodes"] if n["role"] == "analyst")
		assert analyst["active"] is False

		chain = await GLOBAL_ORG_CHART.resolve_chain("default", "researcher")
		assert chain[0] == "researcher"
		assert chain[-1] == "coordinator"

	async def test_top_of_chart_routes(self):
		top = await GLOBAL_ORG_CHART.top_of_chart("default")
		assert top is not None
		manager = await GLOBAL_ORG_CHART.manager_of("default", "executor")
		assert manager is not None and manager.role == "coordinator"
		reports = await GLOBAL_ORG_CHART.reports_of("default", "coordinator")
		assert reports and all(n.reports_to == "coordinator" for n in reports)


class TestAuditTrail:
	async def test_timeline_records_and_filters(self):
		await GLOBAL_AUDIT_LOG.record(
			team_id="default",
			event_type=AuditEventType.INSTRUCTION,
			actor="user",
			recipient="coordinator",
			summary="instruct",
			task_id="t1",
		)
		await GLOBAL_AUDIT_LOG.record(
			team_id="default",
			event_type=AuditEventType.REPLY,
			actor="coordinator",
			recipient="user",
			summary="reply",
			task_id="t2",
		)

		timeline = await GLOBAL_AUDIT_LOG.timeline("default")
		assert {e["summary"] for e in timeline} == {"instruct", "reply"}
		assert timeline[0]["summary"] == "instruct"

		filtered = await GLOBAL_AUDIT_LOG.timeline("default", task_id="t2")
		assert len(filtered) == 1
		assert filtered[0]["summary"] == "reply"


class TestWorkerTick:
	async def test_tick_completes_task_and_emits_city_event(self):
		task = await GLOBAL_TASK_QUEUE.enqueue(
			team_id="default", role="coordinator", subtask="do the thing"
		)
		worker = TaskQueueWorker(team_factory=lambda: _StubOrchestrator("finished!"))
		result = await worker.tick("default")

		assert result.claimed is True
		assert result.error is None
		assert result.task is not None
		assert result.task.status == TaskStatus.DONE
		assert result.task.result == "finished!"

		done = await GLOBAL_TASK_QUEUE.get(task.task_id)
		assert done.status == TaskStatus.DONE

		events = await GLOBAL_AUDIT_LOG.timeline("default", task_id=task.task_id)
		assert len(events) >= 2
		status_events = [e for e in events if e["event_type"] == "status_change"]
		assert any("completed" in e["summary"] for e in status_events)

		async with GLOBAL_TASK_QUEUE._open_session() as s:
			rows = (await s.execute(select(CityEventModel))).scalars().all()
		completed = [r for r in rows if r.event_type == "workqueue.task.completed"]
		assert completed
		assert completed[0].payload["task_id"] == task.task_id

	async def test_tick_failure_marks_task_failed(self):
		task = await GLOBAL_TASK_QUEUE.enqueue(
			team_id="default", role="analyst", subtask="doomed task"
		)

		class _BoomOrchestrator:
			async def run(self, task_: str, session=None):
				raise RuntimeError("exploded")

		worker = TaskQueueWorker(team_factory=lambda: _BoomOrchestrator())
		result = await worker.tick("default")

		assert result.claimed is True
		assert "exploded" in (result.error or "")
		failed = await GLOBAL_TASK_QUEUE.get(task.task_id)
		assert failed.status == TaskStatus.FAILED
		assert "exploded" in (failed.error or "")

		async with GLOBAL_TASK_QUEUE._open_session() as s:
			rows = (await s.execute(select(CityEventModel))).scalars().all()
		assert any(r.event_type == "workqueue.task.failed" for r in rows)

	async def test_tick_with_nothing_queued(self):
		worker = TaskQueueWorker(team_factory=lambda: _StubOrchestrator())
		result = await worker.tick("default")
		assert result.claimed is False


class TestWorkqueueAPI:
	async def test_enqueue_board_audit_flow(self, http_client):
		resp = await http_client.post(
			"/api/v1/workqueue/tasks", json={"subtask": "build the thing"}
		)
		assert resp.status_code == 200
		body = resp.json()
		assert body["status"] == "queued"
		assert body["role"] == "coordinator"

		board = await http_client.get("/api/v1/workqueue/tasks/board")
		assert board.status_code == 200
		columns = board.json()
		assert any(t["task_id"] == body["task_id"] for t in columns["queued"])

		audit = await http_client.get("/api/v1/workqueue/audit")
		assert audit.status_code == 200
		events = audit.json()
		assert any(
			e["task_id"] == body["task_id"] and e["event_type"] == "instruction"
			for e in events
		)

		chart = await http_client.get("/api/v1/workqueue/org-chart")
		assert chart.status_code == 200
		assert chart.json()["top"] is not None
		assert chart.json()["nodes"]

	async def test_org_chart_node_upsert_and_deactivate(self, http_client):
		resp = await http_client.put(
			"/api/v1/workqueue/org-chart/nodes",
			json={"role": "tester", "title": "QA Tester", "reports_to": "coordinator"},
		)
		assert resp.status_code == 200
		assert resp.json()["role"] == "tester"

		chart = await http_client.get("/api/v1/workqueue/org-chart")
		assert any(
			n["role"] == "tester" and n["title"] == "QA Tester"
			for n in chart.json()["nodes"]
		)

		await http_client.delete("/api/v1/workqueue/org-chart/nodes/tester")
		chart2 = await http_client.get("/api/v1/workqueue/org-chart")
		tester = next(n for n in chart2.json()["nodes"] if n["role"] == "tester")
		assert tester["active"] is False

	async def test_tick_endpoint_requires_llm(self, http_client):
		enq = await http_client.post(
			"/api/v1/workqueue/tasks", json={"subtask": "requires llm"}
		)
		assert enq.status_code == 200
		task_id = enq.json()["task_id"]
		resp = await http_client.post(f"/api/v1/workqueue/tasks/{task_id}/tick")
		assert resp.status_code == 503
