"""City commons tools — workspace_*, run_python, emit_viz_event."""

from __future__ import annotations

import time
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import WorkspaceRunStatus
from ..services.city_service import CityService
from .sandbox import SandboxError, run_python_sandboxed, sanitize_workspace_path
from .tools import ToolRegistry, ToolSpec

ALLOWED_VIZ_EVENT_TYPES = frozenset(
    {
        "agent.spawned",
        "artifact.written",
        "run.started",
        "run.finished",
        "job.started",
        "job.completed",
        "cohesion.merge",
        "cohesion.veto",
        "city.pulse.started",
        "city.pulse.finished",
        "city.conduct.started",
        "city.conduct.finished",
        "viz.pulse",
        "viz.custom",
    }
)


def register_city_tools(
    registry: ToolRegistry,
    *,
    db: AsyncSession,
    job_id: UUID,
    agent_id: UUID | None = None,
    timeout_s: float = 15.0,
) -> ToolRegistry:
    """Register build/run commons tools bound to a city job."""

    service = CityService(db)

    async def _require_job() -> dict[str, Any]:
        job = await service.get_job(job_id)
        if job is None:
            raise SandboxError("Job not found")
        return job

    async def workspace_write(**kwargs: Any) -> dict[str, Any]:
        await _require_job()
        path = sanitize_workspace_path(str(kwargs.get("path", "")))
        content = kwargs.get("content")
        if content is None:
            return {"error": "content is required", "status": "denied"}
        content_s = content if isinstance(content, str) else str(content)
        row = await service.record_artifact(
            job_id=job_id,
            path=path,
            content=content_s,
            created_by_agent_id=agent_id,
            content_type=str(kwargs.get("content_type") or "text/plain"),
            metadata={"source": "workspace_write"},
            commit=True,
        )
        return {"ok": True, "artifact": row}

    async def workspace_read(**kwargs: Any) -> dict[str, Any]:
        await _require_job()
        path = sanitize_workspace_path(str(kwargs.get("path", "")))
        art = await service.get_artifact_by_path(job_id, path)
        if art is None:
            return {"ok": False, "found": False, "path": path}
        return {"ok": True, "found": True, "artifact": art}

    async def workspace_list(**kwargs: Any) -> dict[str, Any]:
        await _require_job()
        prefix = kwargs.get("prefix")
        arts = await service.list_artifacts(job_id, limit=int(kwargs.get("limit") or 200))
        if prefix:
            try:
                prefix_s = sanitize_workspace_path(str(prefix))
            except SandboxError:
                prefix_s = str(prefix).strip().strip("/")
            arts = [a for a in arts if str(a["path"]).startswith(prefix_s)]
        # Latest version per path
        latest: dict[str, dict[str, Any]] = {}
        for a in arts:
            prev = latest.get(a["path"])
            if prev is None or int(a["version"]) > int(prev["version"]):
                latest[a["path"]] = a
        paths = sorted(latest.values(), key=lambda x: x["path"])
        return {
            "ok": True,
            "paths": [
                {"path": p["path"], "version": p["version"], "size_bytes": p["size_bytes"]}
                for p in paths
            ],
        }

    async def run_python(**kwargs: Any) -> dict[str, Any]:
        await _require_job()
        started = time.perf_counter()
        path = kwargs.get("path")
        code = kwargs.get("code")
        filename = "main.py"
        source: str | None = None

        if path:
            rel = sanitize_workspace_path(str(path))
            art = await service.get_artifact_by_path(job_id, rel)
            if art is None or art.get("content") is None:
                await service.record_run(
                    job_id=job_id,
                    tool="run_python",
                    args={"path": rel},
                    status=WorkspaceRunStatus.DENIED.value,
                    stderr="artifact not found or empty",
                    duration_ms=int((time.perf_counter() - started) * 1000),
                    started_by_agent_id=agent_id,
                    commit=True,
                )
                return {"ok": False, "status": "denied", "error": "artifact not found or empty"}
            source = str(art["content"])
            filename = rel
        elif code is not None:
            source = code if isinstance(code, str) else str(code)
            filename = sanitize_workspace_path(str(kwargs.get("filename") or "main.py"))
        else:
            return {"ok": False, "status": "denied", "error": "path or code is required"}

        await service.record_run(
            job_id=job_id,
            tool="run_python",
            args={"path": filename if path else None, "inline": code is not None and not path},
            status=WorkspaceRunStatus.RUNNING.value,
            started_by_agent_id=agent_id,
            commit=True,
        )

        # Load sibling artifacts as extra files (best-effort, capped).
        extra: dict[str, str] = {}
        for a in await service.list_artifacts(job_id, limit=50):
            p = str(a["path"])
            if p == filename:
                continue
            if a.get("content") is not None and int(a.get("size_bytes") or 0) < 100_000:
                extra[p] = str(a["content"])

        try:
            result = await run_python_sandboxed(
                source=source,
                filename=filename,
                timeout_s=float(kwargs.get("timeout_s") or timeout_s),
                extra_files=extra or None,
            )
        except SandboxError as exc:
            run = await service.record_run(
                job_id=job_id,
                tool="run_python",
                args={"path": filename},
                status=WorkspaceRunStatus.DENIED.value,
                stderr=str(exc),
                duration_ms=int((time.perf_counter() - started) * 1000),
                started_by_agent_id=agent_id,
                commit=True,
            )
            return {"ok": False, "status": "denied", "error": str(exc), "run": run}

        status_map = {
            "succeeded": WorkspaceRunStatus.SUCCEEDED.value,
            "failed": WorkspaceRunStatus.FAILED.value,
            "timeout": WorkspaceRunStatus.TIMEOUT.value,
        }
        status = status_map.get(str(result.get("status")), WorkspaceRunStatus.FAILED.value)
        duration_ms = int((time.perf_counter() - started) * 1000)
        run = await service.record_run(
            job_id=job_id,
            tool="run_python",
            args={"path": filename},
            status=status,
            stdout=result.get("stdout"),
            stderr=result.get("stderr"),
            duration_ms=duration_ms,
            started_by_agent_id=agent_id,
            artifact_refs=[filename],
            commit=True,
        )
        return {"ok": status == WorkspaceRunStatus.SUCCEEDED.value, "result": result, "run": run}

    async def emit_viz_event(**kwargs: Any) -> dict[str, Any]:
        job = await _require_job()
        event_type = str(kwargs.get("event_type") or kwargs.get("type") or "viz.pulse")
        if event_type not in ALLOWED_VIZ_EVENT_TYPES:
            return {"ok": False, "error": f"event_type not allowed: {event_type}"}
        payload = kwargs.get("payload") if isinstance(kwargs.get("payload"), dict) else {}
        payload = {
            **payload,
            "agent_id": str(agent_id) if agent_id else None,
            "job_id": str(job_id),
        }
        event = await service.emit_event(
            event_type=event_type,
            payload=payload,
            family_id=UUID(job["family_id"]),
            job_id=job_id,
        )
        await db.commit()
        return {
            "ok": True,
            "event": {
                "id": str(event.id),
                "event_type": event.event_type,
                "payload": event.payload,
            },
        }

    registry.register(
        ToolSpec(
            "workspace_write",
            "Write/update a file in the job commons workspace.",
            workspace_write,
            parallel_safe=False,
            tags=["workspace", "city"],
        )
    )
    registry.register(
        ToolSpec(
            "workspace_read",
            "Read a file from the job commons workspace.",
            workspace_read,
            tags=["workspace", "city"],
        )
    )
    registry.register(
        ToolSpec(
            "workspace_list",
            "List files in the job commons workspace.",
            workspace_list,
            tags=["workspace", "city"],
        )
    )
    registry.register(
        ToolSpec(
            "run_python",
            "Run a Python file from commons (or inline code) in a sandbox.",
            run_python,
            parallel_safe=False,
            tags=["run", "city"],
        )
    )
    registry.register(
        ToolSpec(
            "emit_viz_event",
            "Emit a validated visualization event for the city UI.",
            emit_viz_event,
            parallel_safe=False,
            tags=["viz", "city"],
        )
    )
    return registry


async def build_city_registry(
    session_id: str,
    *,
    db: AsyncSession,
    job_id: UUID,
    agent_id: UUID | None = None,
) -> ToolRegistry:
    from .tool_loader import build_team_registry

    registry = await build_team_registry(session_id, db=db, agent_id=agent_id)
    return register_city_tools(registry, db=db, job_id=job_id, agent_id=agent_id)
