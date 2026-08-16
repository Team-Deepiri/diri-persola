"""Shared session-factory plumbing for orchestration stores.

Mirrors the `CityWorkerPool.set_session_factory` injection pattern so tests can
point the global stores at a throwaway in-memory database, while production uses
the process-wide `AsyncSessionLocal` by default.
"""

from __future__ import annotations

from typing import Any, AsyncContextManager, Callable, Optional

from sqlalchemy.ext.asyncio import AsyncSession

SessionFactory = Callable[[], AsyncContextManager[AsyncSession]]


class SessionFactoryMixin:
	"""Mixin giving a store an injectable session factory (default: AsyncSessionLocal)."""

	_session_factory: Optional[SessionFactory] = None

	def set_session_factory(self, factory: Optional[SessionFactory]) -> None:
		"""Inject a session factory (tests) or reset to AsyncSessionLocal (None)."""
		self._session_factory = factory

	def _open_session(self) -> AsyncContextManager[AsyncSession]:
		if self._session_factory is not None:
			return self._session_factory()
		from ..db.database import AsyncSessionLocal

		return AsyncSessionLocal()

	async def _run(
		self,
		session: Optional[AsyncSession],
		fn: Callable[[AsyncSession], Awaitable[Any]],
		*,
		commit: bool,
	) -> Any:
		"""Execute `fn` against a session.

		When `session` is provided the caller owns the transaction (no commit
		here). When omitted the store opens its own session from the injected
		factory and commits before returning if `commit` is True.
		"""
		if session is not None:
			return await fn(session)
		async with self._open_session() as opened:
			result = await fn(opened)
			if commit:
				await opened.commit()
			return result
