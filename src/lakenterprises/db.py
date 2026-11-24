"""Database engine, session factory and helper utilities for LakEnterprises.

Manages SQLAlchemy engine lifecycle, session creation, and database
initialisation for the platform.  Configurable via Settings.db_url.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy import event as sa_event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .config import Settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy-singleton state
# ---------------------------------------------------------------------------

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


def get_engine() -> Engine:
    """Return (and create on first call) the SQLAlchemy engine.

    Uses the database URL from ``Settings``.  For SQLite back-ends WAL
    journal mode and foreign-key enforcement are applied via an event
    listener.
    """
    global _engine
    if _engine is None:
        url = Settings().db_url
        # Ensure the directory for the SQLite file exists.
        if url.startswith("sqlite:///"):
            db_file = url.removeprefix("sqlite:///")
            Path(db_file).parent.mkdir(parents=True, exist_ok=True)
        logger.info("Creating database engine for %s", url)
        _engine = create_engine(
            url,
            echo=False,
            pool_pre_ping=True,
        )
        _configure_sqlite(_engine)
    return _engine


def _configure_sqlite(engine: Engine) -> None:
    """Apply SQLite-specific optimisations (WAL journal)."""

    @sa_event.listens_for(engine, "connect")
    def _on_connect(dbapi_conn: any, connection_record: any) -> None:  # noqa: ANN401
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------


def get_session_factory() -> sessionmaker[Session]:
    """Return (and create on first call) the ``sessionmaker`` bound to the engine."""
    global _session_factory
    if _session_factory is None:
        engine = get_engine()
        _session_factory = sessionmaker(
            bind=engine,
            expire_on_commit=False,
        )
    return _session_factory


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------


def get_db_session() -> Session:
    """Create and return a *new* database session (caller is responsible for closing)."""
    factory = get_session_factory()
    return factory()


def session_scope() -> Generator[Session, None, None]:
    """Context-manager that yields a session and rolls back on exception.

    Usage::

        with session_scope() as session:
            session.add(entity)
    """
    session: Session = get_db_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Database initialisation
# ---------------------------------------------------------------------------


def init_db() -> None:
    """Create all tables defined by the ORM models.

    Ensures every entity class is imported (so its metadata is registered
    with ``Base``) before calling ``Base.metadata.create_all()``.
    """
    engine = get_engine()

    # Force registration of all entity classes with Base.metadata.
    # Importing the module is sufficient – the class bodies execute
    # the DeclarativeBase machinery at definition time.
    from .models.entities import (AuditLog, AuthToken, Document,  # noqa: F401
                                  DocumentChunk, Permission, ResearchSession,
                                  ResearchSubQuestion, Role, User,
                                  WorkflowEvent)

    logger.info("Creating all database tables")
    Base.metadata.create_all(engine)
    logger.info("Database tables created/verified")


def reset_db() -> None:
    """Drop *all* tables and recreate them.

    **Warning:** this permanently destroys all stored data.
    """
    engine = get_engine()

    from .models.entities import (AuditLog, AuthToken, Document,  # noqa: F401
                                  DocumentChunk, Permission, ResearchSession,
                                  ResearchSubQuestion, Role, User,
                                  WorkflowEvent)

    logger.info("Dropping all database tables")
    Base.metadata.drop_all(engine)
    init_db()


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------


def get_db_path() -> str:
    """Return the file-system path to the database.

    For non-SQLite back-ends this returns the full connection string
    as provided by the Settings.
    """
    return str(Settings().db_path)


# ---------------------------------------------------------------------------
# Import Base here for public use and type hints
# ---------------------------------------------------------------------------

from .models.base import Base  # noqa: E402, F401

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "Base",
    "get_engine",
    "get_session_factory",
    "get_db_session",
    "session_scope",
    "init_db",
    "reset_db",
    "get_db_path",
]
