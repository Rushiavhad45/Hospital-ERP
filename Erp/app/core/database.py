"""Async SQLAlchemy engine and session management (SQLite + aiosqlite).

* Foreign keys are enforced per-connection via PRAGMA.
* WAL journal mode gives safe concurrent reads while the app writes.
* ``get_db`` is the single FastAPI dependency that yields a session; it
  rolls back automatically on error. **Repositories never commit** — commits
  happen in the service layer only.
"""
from __future__ import annotations

from pathlib import Path
from typing import AsyncIterator

from sqlalchemy import event
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import (AsyncSession, async_sessionmaker,
                                    create_async_engine)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()


def _ensure_dirs() -> None:
    """Create the SQLite parent folder + upload folder before connecting.

    On a fresh checkout ``data/`` does not exist yet and sqlite3 refuses to
    create intermediate directories ("unable to open database file"),
    especially visible on Windows.
    """
    try:
        db_path = make_url(settings.DATABASE_URL).database
    except Exception:  # pragma: no cover - malformed custom URL
        db_path = None
    if db_path and db_path != ":memory:":
        Path(db_path).expanduser().resolve().parent.mkdir(
            parents=True, exist_ok=True)
    Path(settings.UPLOAD_DIR).expanduser().resolve().mkdir(
        parents=True, exist_ok=True)


_ensure_dirs()

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args={"timeout": 30},
)


@event.listens_for(engine.sync_engine, "connect")
def _sqlite_pragmas(dbapi_connection, _record) -> None:  # pragma: no cover
    cur = dbapi_connection.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.close()


SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Create all tables (no Alembic by design — SQLite dev deployment)."""
    from app import models  # noqa: F401  (register all mappers)

    _ensure_dirs()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
