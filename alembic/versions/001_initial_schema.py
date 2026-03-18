"""Initial schema

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create personas table
    op.create_table('personas',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('creativity', sa.Float(), nullable=False, default=0.5),
        sa.Column('humor', sa.Float(), nullable=False, default=0.5),
        sa.Column('formality', sa.Float(), nullable=False, default=0.5),
        sa.Column('verbosity', sa.Float(), nullable=False, default=0.5),
        sa.Column('empathy', sa.Float(), nullable=False, default=0.5),
        sa.Column('confidence', sa.Float(), nullable=False, default=0.5),
        sa.Column('openness', sa.Float(), nullable=False, default=0.5),
        sa.Column('conscientiousness', sa.Float(), nullable=False, default=0.5),
        sa.Column('extraversion', sa.Float(), nullable=False, default=0.5),
        sa.Column('agreeableness', sa.Float(), nullable=False, default=0.5),
        sa.Column('neuroticism', sa.Float(), nullable=False, default=0.5),
        sa.Column('reasoning_depth', sa.Float(), nullable=False, default=0.5),
        sa.Column('step_by_step', sa.Float(), nullable=False, default=0.5),
        sa.Column('creativity_in_reasoning', sa.Float(), nullable=False, default=0.5),
        sa.Column('synthetics', sa.Float(), nullable=False, default=0.5),
        sa.Column('abstraction', sa.Float(), nullable=False, default=0.5),
        sa.Column('patterns', sa.Float(), nullable=False, default=0.5),
        sa.Column('accuracy', sa.Float(), nullable=False, default=0.8),
        sa.Column('reliability', sa.Float(), nullable=False, default=0.8),
        sa.Column('caution', sa.Float(), nullable=False, default=0.5),
        sa.Column('consistency', sa.Float(), nullable=False, default=0.8),
        sa.Column('self_correction', sa.Float(), nullable=False, default=0.5),
        sa.Column('transparency', sa.Float(), nullable=False, default=0.5),
        sa.Column('system_prompt', sa.Text(), nullable=True),
        sa.Column('model', sa.String(100), nullable=False, default='llama3:8b'),
        sa.Column('temperature', sa.Float(), nullable=False, default=0.7),
        sa.Column('max_tokens', sa.Integer(), nullable=False, default=2000),
        sa.Column('is_preset', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id')
    )

    # Create agents table
    op.create_table('agents',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('role', sa.String(100), nullable=False, default='assistant'),
        sa.Column('model', sa.String(100), nullable=True),
        sa.Column('temperature', sa.Float(), nullable=True),
        sa.Column('max_tokens', sa.Integer(), nullable=True),
        sa.Column('system_prompt', sa.Text(), nullable=True),
        sa.Column('persona_id', sa.String(36), nullable=True),
        sa.Column('tools', sa.JSON(), nullable=False, default=[]),
        sa.Column('memory_enabled', sa.Boolean(), nullable=False, default=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['persona_id'], ['personas.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create sessions table
    op.create_table('sessions',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('agent_id', sa.String(36), nullable=True),
        sa.Column('session_id', sa.String(100), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=False, default={}),
        sa.Column('message_count', sa.Integer(), nullable=False, default=0),
        sa.Column('last_message_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create messages table
    op.create_table('messages',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('session_id', sa.String(36), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('metadata', sa.JSON(), nullable=False, default={}),
        sa.Column('tokens_used', sa.Integer(), nullable=True),
        sa.Column('model', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index('idx_personas_name', 'personas', ['name'])
    op.create_index('idx_personas_is_preset', 'personas', ['is_preset'])
    op.create_index('idx_agents_persona_id', 'agents', ['persona_id'])
    op.create_index('idx_sessions_agent_id', 'sessions', ['agent_id'])
    op.create_index('idx_sessions_session_id', 'sessions', ['session_id'])
    op.create_index('idx_messages_session_id', 'messages', ['session_id'])
    op.create_index('idx_messages_created_at', 'messages', ['created_at'])

    # Add check constraints for data integrity
    op.create_check_constraint('ck_personas_creativity_range', 'personas', 'creativity >= 0.0 AND creativity <= 1.0')
    op.create_check_constraint('ck_personas_humor_range', 'personas', 'humor >= 0.0 AND humor <= 1.0')
    op.create_check_constraint('ck_personas_formality_range', 'personas', 'formality >= 0.0 AND formality <= 1.0')
    op.create_check_constraint('ck_personas_verbosity_range', 'personas', 'verbosity >= 0.0 AND verbosity <= 1.0')
    op.create_check_constraint('ck_personas_empathy_range', 'personas', 'empathy >= 0.0 AND empathy <= 1.0')
    op.create_check_constraint('ck_personas_confidence_range', 'personas', 'confidence >= 0.0 AND confidence <= 1.0')
    op.create_check_constraint('ck_personas_openness_range', 'personas', 'openness >= 0.0 AND openness <= 1.0')
    op.create_check_constraint('ck_personas_conscientiousness_range', 'personas', 'conscientiousness >= 0.0 AND conscientiousness <= 1.0')
    op.create_check_constraint('ck_personas_extraversion_range', 'personas', 'extraversion >= 0.0 AND extraversion <= 1.0')
    op.create_check_constraint('ck_personas_agreeableness_range', 'personas', 'agreeableness >= 0.0 AND agreeableness <= 1.0')
    op.create_check_constraint('ck_personas_neuroticism_range', 'personas', 'neuroticism >= 0.0 AND neuroticism <= 1.0')
    op.create_check_constraint('ck_personas_reasoning_depth_range', 'personas', 'reasoning_depth >= 0.0 AND reasoning_depth <= 1.0')
    op.create_check_constraint('ck_personas_step_by_step_range', 'personas', 'step_by_step >= 0.0 AND step_by_step <= 1.0')
    op.create_check_constraint('ck_personas_creativity_in_reasoning_range', 'personas', 'creativity_in_reasoning >= 0.0 AND creativity_in_reasoning <= 1.0')
    op.create_check_constraint('ck_personas_synthetics_range', 'personas', 'synthetics >= 0.0 AND synthetics <= 1.0')
    op.create_check_constraint('ck_personas_abstraction_range', 'personas', 'abstraction >= 0.0 AND abstraction <= 1.0')
    op.create_check_constraint('ck_personas_patterns_range', 'personas', 'patterns >= 0.0 AND patterns <= 1.0')
    op.create_check_constraint('ck_personas_accuracy_range', 'personas', 'accuracy >= 0.0 AND accuracy <= 1.0')
    op.create_check_constraint('ck_personas_reliability_range', 'personas', 'reliability >= 0.0 AND reliability <= 1.0')
    op.create_check_constraint('ck_personas_caution_range', 'personas', 'caution >= 0.0 AND caution <= 1.0')
    op.create_check_constraint('ck_personas_consistency_range', 'personas', 'consistency >= 0.0 AND consistency <= 1.0')
    op.create_check_constraint('ck_personas_self_correction_range', 'personas', 'self_correction >= 0.0 AND self_correction <= 1.0')
    op.create_check_constraint('ck_personas_transparency_range', 'personas', 'transparency >= 0.0 AND transparency <= 1.0')
    op.create_check_constraint('ck_personas_temperature_range', 'personas', 'temperature >= 0.0 AND temperature <= 2.0')
    op.create_check_constraint('ck_personas_max_tokens_range', 'personas', 'max_tokens >= 1 AND max_tokens <= 32000')
    op.create_check_constraint('ck_messages_role', 'messages', "role IN ('user', 'assistant', 'system')")


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('messages')
    op.drop_table('sessions')
    op.drop_table('agents')
    op.drop_table('personas')