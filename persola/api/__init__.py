"""Persola HTTP API package.

Note: do not ``from .main import main`` here — that shadows the ``persola.api.main``
submodule and breaks ``import persola.api.main``.
"""

from .main import app

__all__ = ["app"]
