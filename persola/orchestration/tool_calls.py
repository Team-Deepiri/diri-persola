"""Parse structured tool calls from agent / LLM text output."""

from __future__ import annotations

import json
import re
from typing import Any


_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)
_TOOL_LINE_RE = re.compile(
	r"TOOL_CALL\s*:\s*([a-zA-Z0-9_]+)\s*\(\s*(\{.*\})\s*\)\s*$",
	re.MULTILINE,
)


def _normalize_calls(raw: Any) -> list[dict[str, Any]]:
	if raw is None:
		return []
	if isinstance(raw, dict):
		if "tool_calls" in raw:
			return _normalize_calls(raw["tool_calls"])
		if "name" in raw:
			args = raw.get("args") or raw.get("arguments") or {}
			if isinstance(args, str):
				try:
					args = json.loads(args)
				except json.JSONDecodeError:
					args = {"value": args}
			return [{"name": str(raw["name"]), "args": args if isinstance(args, dict) else {}}]
		return []
	if isinstance(raw, list):
		out: list[dict[str, Any]] = []
		for item in raw:
			out.extend(_normalize_calls(item))
		return out
	return []


def parse_tool_calls(text: str) -> list[dict[str, Any]]:
	"""
	Extract tool calls from model output.

	Supported forms:
	- JSON object/array with ``tool_calls`` or ``{name, args}``
	- Fenced ```json``` blocks
	- Lines: ``TOOL_CALL: name({"a": 1})``
	"""
	if not text or not text.strip():
		return []

	stripped = text.strip()
	calls: list[dict[str, Any]] = []

	# Whole-message JSON — malformed payloads are skipped (LLM output is noisy).
	if stripped.startswith("{") or stripped.startswith("["):
		try:
			calls.extend(_normalize_calls(json.loads(stripped)))
		except json.JSONDecodeError:
			# Not valid JSON; fall through to fenced / TOOL_CALL line parsers.
			pass

	# Fenced blocks
	for match in _FENCE_RE.finditer(text):
		try:
			calls.extend(_normalize_calls(json.loads(match.group(1))))
		except json.JSONDecodeError:
			# Ignore broken fences; other parsers may still recover calls.
			continue

	# TOOL_CALL lines
	for match in _TOOL_LINE_RE.finditer(text):
		name = match.group(1)
		try:
			args = json.loads(match.group(2))
		except json.JSONDecodeError:
			# Keep the tool name; empty args beats dropping the call entirely.
			args = {}
		if isinstance(args, dict):
			calls.append({"name": name, "args": args})

	# Deduplicate while preserving order
	seen: set[str] = set()
	unique: list[dict[str, Any]] = []
	for call in calls:
		key = json.dumps(call, sort_keys=True, default=str)
		if key in seen:
			continue
		seen.add(key)
		unique.append(call)
	return unique
