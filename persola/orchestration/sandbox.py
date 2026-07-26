"""Path sandbox and sandboxed Python execution for communal city commons."""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path
from typing import Any


class SandboxError(ValueError):
	"""Raised when a path or execution policy is violated."""


def sanitize_workspace_path(user_path: str) -> str:
	"""Normalize a relative workspace path; reject escapes and absolute paths."""
	if not user_path or not str(user_path).strip():
		raise SandboxError("path is required")
	raw = str(user_path).replace("\\", "/").strip()
	if raw.startswith("/") or (len(raw) > 1 and raw[1] == ":"):
		raise SandboxError("absolute paths are denied")
	parts = [p for p in raw.split("/") if p not in ("", ".")]
	if not parts:
		raise SandboxError("path is empty after normalization")
	if any(p == ".." for p in parts):
		raise SandboxError("path escape (..) is denied")
	if any(p.startswith("~") for p in parts):
		raise SandboxError("home-relative paths are denied")
	return "/".join(parts)


def resolve_under_root(root: Path, user_path: str) -> Path:
	"""Resolve user_path under root; raise SandboxError on escape."""
	rel = sanitize_workspace_path(user_path)
	root_resolved = root.resolve()
	full = (root_resolved / rel).resolve()
	try:
		full.relative_to(root_resolved)
	except ValueError as exc:
		raise SandboxError("path escapes workspace root") from exc
	return full


DEFAULT_RUN_TIMEOUT_S = 15.0
DEFAULT_OUTPUT_CAP = 32_768


async def run_python_sandboxed(
	*,
	source: str,
	filename: str = "main.py",
	timeout_s: float = DEFAULT_RUN_TIMEOUT_S,
	output_cap: int = DEFAULT_OUTPUT_CAP,
	extra_files: dict[str, str] | None = None,
) -> dict[str, Any]:
	"""
	Execute Python source in an isolated temp directory.

	Network is best-effort denied by clearing proxy env vars and using
	``python -I`` (isolated mode). Wall-clock timeout and stdout/stderr caps apply.
	"""
	rel_name = sanitize_workspace_path(filename)
	with tempfile.TemporaryDirectory(prefix="persola-city-") as tmp:
		root = Path(tmp)
		script_path = resolve_under_root(root, rel_name)
		script_path.parent.mkdir(parents=True, exist_ok=True)
		script_path.write_text(source, encoding="utf-8")

		for path, content in (extra_files or {}).items():
			target = resolve_under_root(root, path)
			target.parent.mkdir(parents=True, exist_ok=True)
			target.write_text(content, encoding="utf-8")

		env = {
			"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
			"HOME": str(root),
			"TMPDIR": str(root),
			"PYTHONDONTWRITEBYTECODE": "1",
			"PYTHONNOUSERSITE": "1",
			"LANG": "C.UTF-8",
		}
		# Strip proxy / network-ish env that child might inherit.
		for key in list(os.environ):
			upper = key.upper()
			if upper.endswith("_PROXY") or upper in {"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"}:
				continue

		proc = await asyncio.create_subprocess_exec(
			sys.executable,
			"-I",
			"-B",
			str(script_path),
			stdout=asyncio.subprocess.PIPE,
			stderr=asyncio.subprocess.PIPE,
			cwd=str(root),
			env=env,
		)
		try:
			stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
		except asyncio.TimeoutError:
			proc.kill()
			await proc.communicate()
			return {
				"status": "timeout",
				"stdout": "",
				"stderr": f"execution exceeded {timeout_s}s",
				"returncode": None,
				"duration_ms": int(timeout_s * 1000),
				"truncated": True,
			}

		stdout = (stdout_b or b"").decode("utf-8", errors="replace")
		stderr = (stderr_b or b"").decode("utf-8", errors="replace")
		truncated = False
		if len(stdout) > output_cap:
			stdout = stdout[:output_cap] + "\n...[truncated]"
			truncated = True
		if len(stderr) > output_cap:
			stderr = stderr[:output_cap] + "\n...[truncated]"
			truncated = True

		ok = proc.returncode == 0
		return {
			"status": "succeeded" if ok else "failed",
			"stdout": stdout,
			"stderr": stderr,
			"returncode": proc.returncode,
			"truncated": truncated,
		}
