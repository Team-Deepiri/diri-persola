"""
Database settings — loaded from environment / .env file.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings


class DBSettings(BaseSettings):
    database_url: str = "postgresql+asyncpg://deepiri:deepiripassword@persola-db:5433/persola"
    db_echo: bool = False
    db_pool_size: int = 5
    db_max_overflow: int = 10

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_db_settings() -> DBSettings:
    return DBSettings()