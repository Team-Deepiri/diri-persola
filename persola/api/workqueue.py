"""Work queue API — org chart, kanban board, and audit trail.

This is the productivity surface modeled on Alook: define an org chart,
drop a task on the top of it, watch it fan out to specialists and get
picked up autonomously, and read back a full audit trail of who did what.
Complements ``teams.py`` (synchronous /invoke) with the async path.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..integrations.llm import get_llm_provider
from ..orchestration.audit_log import GLOBAL_AUDIT_LOG, AuditEventType
from ..orchestration.daemon import TaskQueueWorker
from ..orchestration.org_chart import GLOBAL_ORG_CHART, OrgNode
from ..orchestration.task_queue import GLOBAL_TASK_QUEUE
from ..orchestration.team import TeamOrchestrator

router = APIRouter(prefix="/api/v1/workqueue", tags=["workqueue"])


# ---------------------------------------------------------------- org chart


@router.get("/org-chart")
async def get_org_chart(team_id: str = "default"):
    return GLOBAL_ORG_CHART.to_dict(team_id)


class OrgNodeRequest(BaseModel):
    role: str
    title: str
    reports_to: str | None = None
    email: str | None = None


@router.put("/org-chart/nodes")
async def upsert_org_node(body: OrgNodeRequest, team_id: str = "default"):
    node = GLOBAL_ORG_CHART.upsert_node(
        team_id,
        OrgNode(role=body.role, title=body.title, reports_to=body.reports_to, email=body.email),
    )
    return node.to_dict()


@router.delete("/org-chart/nodes/{role}")
async def deactivate_org_node(role: str, team_id: str = "default"):
    GLOBAL_ORG_CHART.deactivate(team_id, role)
    return {"role": role, "active": False}


# --------------------------------------------------------------- task board


class EnqueueTaskRequest(BaseModel):
    subtask: str = Field(..., min_length=1)
    role: str | None = None  # default: top of org chart, mirrors "assign to the CEO's inbox"
    origin: str = "user"
    session_id: str | None = None


@router.post("/tasks")
async def enqueue_task(body: EnqueueTaskRequest, team_id: str = "default"):
    role = body.role
    if role is None:
        top = GLOBAL_ORG_CHART.top_of_chart(team_id)
        role = top.role if top else "coordinator"
    task = GLOBAL_TASK_QUEUE.enqueue(
        team_id=team_id,
        role=role,
        subtask=body.subtask,
        origin=body.origin,
        session_id=body.session_id,
    )
    GLOBAL_AUDIT_LOG.record(
        team_id=team_id,
        event_type=AuditEventType.INSTRUCTION,
        actor=body.origin,
        recipient=role,
        summary=body.subtask[:280],
        task_id=task.task_id,
        session_id=body.session_id,
    )
    return task.to_dict()


@router.get("/tasks/board")
async def get_board(team_id: str = "default"):
    return GLOBAL_TASK_QUEUE.board(team_id)


@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    task = GLOBAL_TASK_QUEUE.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task.to_dict()


@router.post("/tasks/{task_id}/tick")
async def tick_single_task(task_id: str, team_id: str = "default"):
    """Force-process one specific task now, instead of waiting on the poller."""
    task = GLOBAL_TASK_QUEUE.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status.value != "queued":
        return task.to_dict()

    llm = get_llm_provider()
    if not llm.is_available():
        raise HTTPException(status_code=503, detail="No LLM provider available")

    async def llm_fn(system: str, user: str) -> str:
        return await llm.chat([{"role": "user", "content": user}], system_prompt=system)

    worker = TaskQueueWorker(team_factory=lambda: TeamOrchestrator(llm_fn=llm_fn), role=task.role)
    result = await worker.tick(team_id)
    if result.task is None:
        raise HTTPException(
            status_code=409, detail="Task was claimed by another worker before this tick"
        )
    return result.task.to_dict()


# ---------------------------------------------------------------- audit log


@router.get("/audit")
async def get_audit_trail(
    team_id: str = "default",
    session_id: str | None = None,
    task_id: str | None = None,
    limit: int = 200,
):
    return GLOBAL_AUDIT_LOG.timeline(team_id, session_id=session_id, task_id=task_id, limit=limit)
