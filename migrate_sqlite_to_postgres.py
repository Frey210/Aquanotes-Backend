"""
Utility script to copy every table from the legacy SQLite database into
the PostgreSQL database defined by ``DATABASE_URL``.

Usage:
    python migrate_sqlite_to_postgres.py

Environment variables:
    DATABASE_URL  - required; PostgreSQL SQLAlchemy URL
    SQLITE_URL    - optional; defaults to sqlite:///./aquanotes.db
"""

from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from typing import Generator, Iterable, Sequence, Type

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.orm.decl_api import DeclarativeMeta

from app import models
from app.database import Base

BATCH_SIZE = 500
SQLITE_URL = os.getenv("SQLITE_URL", "sqlite:///./aquanotes.db")
POSTGRES_URL = os.getenv("DATABASE_URL")

if not POSTGRES_URL:
    sys.exit(
        "DATABASE_URL is not set. Export your PostgreSQL connection string before running this script."
    )


def build_engine(url: str):
    return create_engine(url, pool_pre_ping=True)


@contextmanager
def session_scope(session: Session) -> Generator[Session, None, None]:
    try:
        yield session
        session.commit()
    except Exception:  # pragma: no cover - smoke script
        session.rollback()
        raise
    finally:
        session.close()


def iter_model_columns(model: DeclarativeMeta) -> Sequence[str]:
    return [column.name for column in model.__table__.columns]  # type: ignore[attr-defined]


def copy_rows(
    source: Session, target: Session, model: Type[DeclarativeMeta], batch_size: int = BATCH_SIZE
) -> int:
    columns = iter_model_columns(model)
    total = 0

    query = source.query(model)
    for row in query.yield_per(batch_size):
        payload = {column: getattr(row, column) for column in columns}
        target.merge(model(**payload))  # merge keeps PK/unique values from SQLite
        total += 1

        if total % batch_size == 0:
            target.flush()

    target.flush()
    return total


def migration_order() -> Iterable[Type[DeclarativeMeta]]:
    """
    Order matters because of foreign-key constraints.
    """
    return (
        models.User,
        models.AuthToken,
        models.Tambak,
        models.Device,
        models.Kolam,
        models.SensorData,
        models.Notification,
    )


def main() -> None:
    print(f"Reading from SQLite URL: {SQLITE_URL}")
    print(f"Writing to PostgreSQL URL: {POSTGRES_URL}")

    source_engine = build_engine(SQLITE_URL)
    target_engine = build_engine(POSTGRES_URL)

    Base.metadata.create_all(bind=target_engine)

    SourceSession = sessionmaker(bind=source_engine, autoflush=False, autocommit=False)
    TargetSession = sessionmaker(bind=target_engine, autoflush=False, autocommit=False)

    with session_scope(SourceSession()) as source_session, session_scope(
        TargetSession()
    ) as target_session:
        for model in migration_order():
            count = copy_rows(source_session, target_session, model)
            print(f"Copied {count:>5} rows -> {model.__tablename__}")

    print("Migration complete.")


if __name__ == "__main__":
    main()
