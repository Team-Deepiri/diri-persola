"""Disk commons mirror — optional filesystem shadow of job artifacts (Phase 9)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from uuid import UUID

from .sandbox import resolve_under_root, sanitize_workspace_path


def commons_root() -> Path | None:
    """Return configured commons root, or None if mirroring is disabled."""
    raw = os.getenv("PERSOLA_CITY_COMMONS_ROOT", "").strip()
    if not raw:
        return None
    return Path(raw).expanduser()


def job_commons_dir(job_id: UUID | str, *, root: Path | None = None) -> Path | None:
    base = root if root is not None else commons_root()
    if base is None:
        return None
    return base / "jobs" / str(job_id)


def mirror_artifact(
    *,
    job_id: UUID | str,
    path: str,
    content: str | None,
    root: Path | None = None,
) -> dict[str, Any]:
    """
    Write artifact content under ``PERSOLA_CITY_COMMONS_ROOT/jobs/{job_id}/...``.

    No-op (``mirrored: false``) when the env root is unset. Path escapes are denied.
    """
    base = job_commons_dir(job_id, root=root)
    if base is None:
        return {"mirrored": False, "reason": "PERSOLA_CITY_COMMONS_ROOT unset"}

    rel = sanitize_workspace_path(path)
    base.mkdir(parents=True, exist_ok=True)
    target = resolve_under_root(base, rel)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content or "", encoding="utf-8")
    return {
        "mirrored": True,
        "root": str(base),
        "path": rel,
        "absolute": str(target),
        "bytes": len((content or "").encode("utf-8")),
    }


def list_mirrored_files(job_id: UUID | str, *, root: Path | None = None) -> list[str]:
    base = job_commons_dir(job_id, root=root)
    if base is None or not base.exists():
        return []
    files: list[str] = []
    for p in sorted(base.rglob("*")):
        if p.is_file():
            files.append(str(p.relative_to(base)).replace("\\", "/"))
    return files


def mirror_status(*, root: Path | None = None) -> dict[str, Any]:
    base = root if root is not None else commons_root()
    enabled = base is not None
    return {
        "enabled": enabled,
        "root": str(base) if base else None,
        "exists": bool(base and base.exists()),
        "env": "PERSOLA_CITY_COMMONS_ROOT",
    }
