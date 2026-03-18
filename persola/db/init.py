# Database layer exports
# Re-export models, schemas, repositories, services for easy importing

# Models
from .models import (
    Base,
    PersonaModel,
    AgentModel,
    SessionModel,
    MessageModel,
    PersonaPresetModel,
)

# Schemas
from .schemas import (
    MessageRole,
    PersonaBase,
    PersonaCreate,
    PersonaUpdate,
    PersonaResponse,
    AgentBase,
    AgentCreate,
    AgentUpdate,
    AgentResponse,
    AgentWithPersonaResponse,
    SessionBase,
    SessionCreate,
    SessionUpdate,
    SessionResponse,
    MessageBase,
    MessageCreate,
    MessageResponse,
    PersonaPresetBase,
    PersonaPresetCreate,
    PersonaPresetUpdate,
    PersonaPresetResponse,
    PaginationParams,
    PaginatedResponse,
    PersonaSearchParams,
    SessionFilterParams,
    MessageSearchParams,
)

# Database
from .database import (
    engine,
    async_session,
    get_db,
    health_check,
    init_database,
    close_database,
    reset_database,
)

# Repositories
from .repositories.base import BaseRepository
from .repositories.persona_repository import PersonaRepository
from .repositories.agent_repository import AgentRepository
from .repositories.session_repository import SessionRepository
from .repositories.message_repository import MessageRepository

# Services
from .services.persona_service import PersonaService
from .services.agent_service import AgentService
from .services.analytics_service import AnalyticsService

# Re-export from persola.models for compatibility
from ..models import (
    PersonaProfile,
    AgentConfig,
    KNOB_DEFINITIONS,
    PresetName,
    DEFAULT_PRESETS,
)

__all__ = [
    # Models
    "Base",
    "PersonaModel",
    "AgentModel",
    "SessionModel",
    "MessageModel",
    "PersonaPresetModel",

    # Schemas
    "MessageRole",
    "PersonaBase",
    "PersonaCreate",
    "PersonaUpdate",
    "PersonaResponse",
    "AgentBase",
    "AgentCreate",
    "AgentUpdate",
    "AgentResponse",
    "AgentWithPersonaResponse",
    "SessionBase",
    "SessionCreate",
    "SessionUpdate",
    "SessionResponse",
    "MessageBase",
    "MessageCreate",
    "MessageResponse",
    "PersonaPresetBase",
    "PersonaPresetCreate",
    "PersonaPresetUpdate",
    "PersonaPresetResponse",
    "PaginationParams",
    "PaginatedResponse",
    "PersonaSearchParams",
    "SessionFilterParams",
    "MessageSearchParams",

    # Database
    "engine",
    "async_session",
    "get_db",
    "health_check",
    "init_database",
    "close_database",
    "reset_database",

    # Repositories
    "BaseRepository",
    "PersonaRepository",
    "AgentRepository",
    "SessionRepository",
    "MessageRepository",

    # Services
    "PersonaService",
    "AgentService",
    "AnalyticsService",

    # Compatibility exports
    "PersonaProfile",
    "AgentConfig",
    "KNOB_DEFINITIONS",
    "PresetName",
    "DEFAULT_PRESETS",
]