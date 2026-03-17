from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import Base, SessionLocal, get_engine, get_sqlite_path
from .db_models import Item


def main() -> None:
    engine = get_engine()

    Base.metadata.create_all(engine)

    SessionLocal.configure(bind=engine)
    with SessionLocal() as session:  # type: Session
        row = Item(name="hello")
        session.add(row)
        session.commit()
        session.refresh(row)

        fetched = session.scalar(select(Item).where(Item.id == row.id))

    print(
        {
            "db_path": str(get_sqlite_path()),
            "inserted_id": row.id,
            "inserted_name": row.name,
            "fetched": {"id": fetched.id, "name": fetched.name} if fetched else None,
        }
    )


if __name__ == "__main__":
    main()

