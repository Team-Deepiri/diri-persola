"""Shared time helpers.

Centralises naive-UTC timestamp generation so model defaults and orchestration
stores stay consistent instead of each redefining a local ``_utcnow``.
"""

from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
	"""Return the current UTC time as a timezone-aware ``datetime``."""
	return datetime.now(timezone.utc)
