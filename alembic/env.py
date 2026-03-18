import asyncio
import os
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
fileConfig(config.config_file_name)

def get_url():
    return os.getenv("DB_URL", "postgresql+asyncpg://postgres:postgres@localhost:5433/persola")

config.set_main_option("sqlalchemy.url", get_url())

# Import your models here
from persola.models import *

target_metadata = None
try:
    from persola.models import Base
    target_metadata = Base.metadata
except Exception:
    target_metadata = None

def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"}
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = create_async_engine(get_url(), poolclass=pool.NullPool)
    async def do_run_migrations(connection: Connection):
        await connection.run_sync(
            lambda sync_conn: context.configure(
                connection=sync_conn, target_metadata=target_metadata
            )
        )
        with context.begin_transaction():
            context.run_migrations()
    async with connectable.connect() as connection:
        await do_run_migrations(connection)
    await connectable.dispose()

def run():
    if context.is_offline_mode():
        run_migrations_offline()
    else:
        asyncio.run(run_migrations_online())

run()
