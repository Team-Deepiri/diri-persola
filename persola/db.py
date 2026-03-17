from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def get_sqlite_path() -> Path:
    # Keep it simple: a local file DB in the project root.
    return Path(__file__).resolve().parents[1] / "persola.sqlite3"


def get_engine(sqlite_path: Path | None = None) -> Engine:
    path = sqlite_path or get_sqlite_path()
    # `future=True` is implicit in SQLAlchemy 2.x; included for clarity.
    return create_engine(f"sqlite:///{path.as_posix()}", future=True)


SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False)

