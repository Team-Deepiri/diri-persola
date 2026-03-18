from pydantic import BaseModel, Field, validator, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
import uuid


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class PersonaBase(BaseModel):
    """Base schema for persona data."""
    name: str = Field(..., max_length=255)
    description: Optional[str] = None

    # Tuning parameters with validation
    creativity: float = Field(0.5, ge=0.0, le=1.0)
    humor: float = Field(0.5, ge=0.0, le=1.0)
    formality: float = Field(0.5, ge=0.0, le=1.0)
    verbosity: float = Field(0.5, ge=0.0, le=1.0)
    empathy: float = Field(0.5, ge=0.0, le=1.0)
    confidence: float = Field(0.5, ge=0.0, le=1.0)

    openness: float = Field(0.5, ge=0.0, le=1.0)
    conscientiousness: float = Field(0.5, ge=0.0, le=1.0)
    extraversion: float = Field(0.5, ge=0.0, le=1.0)
    agreeableness: float = Field(0.5, ge=0.0, le=1.0)
    neuroticism: float = Field(0.5, ge=0.0, le=1.0)

    reasoning_depth: float = Field(0.5, ge=0.0, le=1.0)
    step_by_step: float = Field(0.5, ge=0.0, le=1.0)
    creativity_in_reasoning: float = Field(0.5, ge=0.0, le=1.0)
    synthetics: float = Field(0.5, ge=0.0, le=1.0)
    abstraction: float = Field(0.5, ge=0.0, le=1.0)
    patterns: float = Field(0.5, ge=0.0, le=1.0)

    accuracy: float = Field(0.8, ge=0.0, le=1.0)
    reliability: float = Field(0.8, ge=0.0, le=1.0)
    caution: float = Field(0.5, ge=0.0, le=1.0)
    consistency: float = Field(0.8, ge=0.0, le=1.0)
    self_correction: float = Field(0.5, ge=0.0, le=1.0)
    transparency: float = Field(0.5, ge=0.0, le=1.0)

    system_prompt: Optional[str] = None
    model: str = Field("llama3:8b", max_length=255)
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(2000, ge=1, le=32000)


class PersonaCreate(PersonaBase):
    """Schema for creating a new persona."""
    pass


class PersonaUpdate(BaseModel):
    """Schema for updating an existing persona."""
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None

    creativity: Optional[float] = Field(None, ge=0.0, le=1.0)
    humor: Optional[float] = Field(None, ge=0.0, le=1.0)
    formality: Optional[float] = Field(None, ge=0.0, le=1.0)
    verbosity: Optional[float] = Field(None, ge=0.0, le=1.0)
    empathy: Optional[float] = Field(None, ge=0.0, le=1.0)
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)

    openness: Optional[float] = Field(None, ge=0.0, le=1.0)
    conscientiousness: Optional[float] = Field(None, ge=0.0, le=1.0)
    extraversion: Optional[float] = Field(None, ge=0.0, le=1.0)
    agreeableness: Optional[float] = Field(None, ge=0.0, le=1.0)
    neuroticism: Optional[float] = Field(None, ge=0.0, le=1.0)

    reasoning_depth: Optional[float] = Field(None, ge=0.0, le=1.0)
    step_by_step: Optional[float] = Field(None, ge=0.0, le=1.0)
    creativity_in_reasoning: Optional[float] = Field(None, ge=0.0, le=1.0)
    synthetics: Optional[float] = Field(None, ge=0.0, le=1.0)
    abstraction: Optional[float] = Field(None, ge=0.0, le=1.0)
    patterns: Optional[float] = Field(None, ge=0.0, le=1.0)

    accuracy: Optional[float] = Field(None, ge=0.0, le=1.0)
    reliability: Optional[float] = Field(None, ge=0.0, le=1.0)
    caution: Optional[float] = Field(None, ge=0.0, le=1.0)
    consistency: Optional[float] = Field(None, ge=0.0, le=1.0)
    self_correction: Optional[float] = Field(None, ge=0.0, le=1.0)
    transparency: Optional[float] = Field(None, ge=0.0, le=1.0)

    system_prompt: Optional[str] = None
    model: Optional[str] = Field(None, max_length=255)
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1, le=32000)


class PersonaResponse(PersonaBase):
    """Schema for persona response data."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime


class AgentBase(BaseModel):
    """Base schema for agent data."""
    name: str = Field(..., max_length=255)
    config: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class AgentCreate(AgentBase):
    """Schema for creating a new agent."""
    persona_id: str


class AgentUpdate(BaseModel):
    """Schema for updating an existing agent."""
    name: Optional[str] = Field(None, max_length=255)
    config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class AgentResponse(AgentBase):
    """Schema for agent response data."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    persona_id: str
    created_at: datetime
    updated_at: datetime


class AgentWithPersonaResponse(AgentResponse):
    """Agent response including persona data."""
    persona: PersonaResponse


class SessionBase(BaseModel):
    """Base schema for session data."""
    user_id: Optional[str] = None
    metadata_: Optional[Dict[str, Any]] = Field(default_factory=dict, alias="metadata")


class SessionCreate(SessionBase):
    """Schema for creating a new session."""
    persona_id: str
    agent_id: Optional[str] = None


class SessionUpdate(BaseModel):
    """Schema for updating an existing session."""
    ended_at: Optional[datetime] = None
    metadata_: Optional[Dict[str, Any]] = Field(None, alias="metadata")


class SessionResponse(SessionBase):
    """Schema for session response data."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    persona_id: str
    agent_id: Optional[str] = None
    started_at: datetime
    ended_at: Optional[datetime] = None


class MessageBase(BaseModel):
    """Base schema for message data."""
    role: MessageRole
    content: str
    metadata_: Optional[Dict[str, Any]] = Field(default_factory=dict, alias="metadata")


class MessageCreate(MessageBase):
    """Schema for creating a new message."""
    session_id: str


class MessageResponse(MessageBase):
    """Schema for message response data."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    timestamp: datetime


class PersonaPresetBase(BaseModel):
    """Base schema for persona preset data."""
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    preset_data: Dict[str, Any]
    is_default: bool = False


class PersonaPresetCreate(PersonaPresetBase):
    """Schema for creating a new preset."""
    pass


class PersonaPresetUpdate(BaseModel):
    """Schema for updating an existing preset."""
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    preset_data: Optional[Dict[str, Any]] = None
    is_default: Optional[bool] = None


class PersonaPresetResponse(PersonaPresetBase):
    """Schema for preset response data."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime


# Pagination schemas
class PaginationParams(BaseModel):
    """Parameters for pagination."""
    skip: int = Field(0, ge=0)
    limit: int = Field(50, ge=1, le=1000)


class PaginatedResponse(BaseModel):
    """Generic paginated response."""
    items: List[Any]
    total: int
    skip: int
    limit: int


# Search and filter schemas
class PersonaSearchParams(BaseModel):
    """Parameters for persona search."""
    query: Optional[str] = None
    skip: int = 0
    limit: int = 50


class SessionFilterParams(BaseModel):
    """Parameters for session filtering."""
    persona_id: Optional[str] = None
    agent_id: Optional[str] = None
    user_id: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    skip: int = 0
    limit: int = 50


class MessageSearchParams(BaseModel):
    """Parameters for message search."""
    session_id: Optional[str] = None
    query: Optional[str] = None
    role: Optional[MessageRole] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    skip: int = 0
    limit: int = 50