"""The relational database: organisations, users, subscriptions, sessions.

SQLite by default, in RUNTIME_DIR. ``DATABASE_URL`` switches it to any
database SQLAlchemy supports — ``postgresql+psycopg://user:pass@host/db`` —
without touching anything else.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

from utils.config import load_env  # noqa: F401  (loads .env before DATABASE_URL is read)
from utils.paths import RUNTIME_DIR

DATABASE_URL = os.getenv("DATABASE_URL") or f"sqlite:///{(RUNTIME_DIR / 'platform.db').as_posix()}"

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args)

if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _sqlite_foreign_keys(dbapi_connection, _record) -> None:
        # SQLite ignores foreign keys unless each connection asks for them.
        dbapi_connection.execute("PRAGMA foreign_keys=ON")


def init_db() -> None:
    from database import tables  # noqa: F401  (registers the tables)
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
