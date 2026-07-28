"""
Deprecated dual-ORM module.

City + Alembic use ``persola.db.models`` exclusively. This module used to define
a parallel ``PersonaRow`` / ``AgentRow`` schema with string primary keys that
could not share metadata with the UUID city schema.

Import aliases remain so old ``from persola.db.tables import PersonaRow`` lines
resolve to the canonical models. Prefer ``persola.db.models`` directly.
"""

from __future__ import annotations

import warnings

from .models import AgentModel as AgentRow
from .models import PersonaModel as PersonaRow

warnings.warn(
	"persola.db.tables is deprecated; import PersonaModel/AgentModel from persola.db.models",
	DeprecationWarning,
	stacklevel=2,
)

__all__ = ["PersonaRow", "AgentRow"]
