"""Workflow and session state for multi-agent runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class WorkflowStepRecord:
    step_id: str
    role: str
    task: str
    output: str
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    started_at: datetime = field(default_factory=_utcnow)
    completed_at: Optional[datetime] = None


@dataclass
class WorkflowState:
    workflow_id: str = field(default_factory=lambda: str(uuid4()))
    goal: str = ""
    steps: List[WorkflowStepRecord] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"

    def add_step(self, role: str, task: str, output: str, tool_calls: Optional[List[Dict[str, Any]]] = None) -> None:
        self.steps.append(
            WorkflowStepRecord(
                step_id=str(uuid4()),
                role=role,
                task=task,
                output=output,
                tool_calls=tool_calls or [],
                completed_at=_utcnow(),
            )
        )
        self.status = "running"

    def complete(self) -> None:
        self.status = "completed"

    def fail(self, reason: str) -> None:
        self.context["error"] = reason
        self.status = "failed"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "goal": self.goal,
            "status": self.status,
            "context": self.context,
            "steps": [
                {
                    "step_id": s.step_id,
                    "role": s.role,
                    "task": s.task,
                    "output": s.output,
                    "tool_calls": s.tool_calls,
                    "started_at": s.started_at.isoformat(),
                    "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                }
                for s in self.steps
            ],
        }


@dataclass
class TeamSessionState:
    session_id: str = field(default_factory=lambda: str(uuid4()))
    team_id: str = ""
    messages: List[Dict[str, str]] = field(default_factory=list)
    memory_snapshot: Dict[str, Any] = field(default_factory=dict)
    active_workflow: Optional[WorkflowState] = None
    created_at: datetime = field(default_factory=_utcnow)

    def append_message(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "team_id": self.team_id,
            "messages": self.messages,
            "memory_snapshot": self.memory_snapshot,
            "active_workflow": self.active_workflow.to_dict() if self.active_workflow else None,
            "created_at": self.created_at.isoformat(),
        }
