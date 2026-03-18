import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Text, DateTime, Float, JSON, ForeignKey, Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

def generate_uuid():
    return str(uuid.uuid4())

class PersonaModel(Base):
    __tablename__ = 'personas'
    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    # Tuning parameters
    creativity = Column(Float, default=0.5)
    humor = Column(Float, default=0.5)
    formality = Column(Float, default=0.5)
    verbosity = Column(Float, default=0.5)
    empathy = Column(Float, default=0.5)
    confidence = Column(Float, default=0.5)
    openness = Column(Float, default=0.5)
    conscientiousness = Column(Float, default=0.5)
    extraversion = Column(Float, default=0.5)
    agreeableness = Column(Float, default=0.5)
    neuroticism = Column(Float, default=0.5)
    reasoning_depth = Column(Float, default=0.5)
    step_by_step = Column(Float, default=0.5)
    creativity_in_reasoning = Column(Float, default=0.5)
    synthetics = Column(Float, default=0.5)
    abstraction = Column(Float, default=0.5)
    patterns = Column(Float, default=0.5)
    accuracy = Column(Float, default=0.8)
    reliability = Column(Float, default=0.8)
    caution = Column(Float, default=0.5)
    consistency = Column(Float, default=0.8)
    self_correction = Column(Float, default=0.5)
    transparency = Column(Float, default=0.5)
    # Relationships
    agents = relationship('AgentModel', back_populates='persona', cascade="all, delete-orphan")
    presets = relationship('PersonaPresetModel', back_populates='persona', cascade="all, delete-orphan")

    __table_args__ = (
        Index('ix_personas_name', 'name'),
    )

class AgentModel(Base):
    __tablename__ = 'agents'
    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    persona_id = Column(UUID(as_uuid=False), ForeignKey('personas.id'), nullable=False)
    config = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    persona = relationship('PersonaModel', back_populates='agents')
    sessions = relationship('SessionModel', back_populates='agent', cascade="all, delete-orphan")

    __table_args__ = (
        Index('ix_agents_persona_id', 'persona_id'),
    )

class SessionModel(Base):
    __tablename__ = 'sessions'
    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    agent_id = Column(UUID(as_uuid=False), ForeignKey('agents.id'), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    agent = relationship('AgentModel', back_populates='sessions')
    messages = relationship('MessageModel', back_populates='session', cascade="all, delete-orphan")

    __table_args__ = (
        Index('ix_sessions_agent_id', 'agent_id'),
    )

class MessageModel(Base):
    __tablename__ = 'conversation_history'
    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    session_id = Column(UUID(as_uuid=False), ForeignKey('sessions.id'), nullable=False)
    message = Column(Text, nullable=False)
    sender = Column(String(32), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    session = relationship('SessionModel', back_populates='messages')

    __table_args__ = (
        Index('ix_conversation_history_session_id', 'session_id'),
        Index('ix_conversation_history_timestamp', 'timestamp'),
    )

class PersonaPresetModel(Base):
    __tablename__ = 'persona_presets'
    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    persona_id = Column(UUID(as_uuid=False), ForeignKey('personas.id'), nullable=False)
    name = Column(String(128), nullable=False)
    config = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    persona = relationship('PersonaModel', back_populates='presets')

    __table_args__ = (
        Index('ix_persona_presets_persona_id', 'persona_id'),
        Index('ix_persona_presets_name', 'name'),
    )
