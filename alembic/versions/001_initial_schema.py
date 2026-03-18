"""
Initial schema for persola
"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table(
        'personas',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )
    op.create_index('ix_personas_name', 'personas', ['name'])

    op.create_table(
        'agents',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('persona_id', sa.String(length=64), sa.ForeignKey('personas.id'), nullable=False),
        sa.Column('config', sa.JSON, nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )
    op.create_index('ix_agents_persona_id', 'agents', ['persona_id'])

    op.create_table(
        'sessions',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('agent_id', sa.String(length=64), sa.ForeignKey('agents.id'), nullable=False),
        sa.Column('started_at', sa.DateTime, nullable=False),
        sa.Column('ended_at', sa.DateTime, nullable=True),
    )
    op.create_index('ix_sessions_agent_id', 'sessions', ['agent_id'])

    op.create_table(
        'conversation_history',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('session_id', sa.String(length=64), sa.ForeignKey('sessions.id'), nullable=False),
        sa.Column('message', sa.Text, nullable=False),
        sa.Column('sender', sa.String(length=32), nullable=False),
        sa.Column('timestamp', sa.DateTime, nullable=False),
    )
    op.create_index('ix_conversation_history_session_id', 'conversation_history', ['session_id'])
    op.create_index('ix_conversation_history_timestamp', 'conversation_history', ['timestamp'])

def downgrade():
    op.drop_index('ix_conversation_history_timestamp', table_name='conversation_history')
    op.drop_index('ix_conversation_history_session_id', table_name='conversation_history')
    op.drop_table('conversation_history')
    op.drop_index('ix_sessions_agent_id', table_name='sessions')
    op.drop_table('sessions')
    op.drop_index('ix_agents_persona_id', table_name='agents')
    op.drop_table('agents')
    op.drop_index('ix_personas_name', table_name='personas')
    op.drop_table('personas')
