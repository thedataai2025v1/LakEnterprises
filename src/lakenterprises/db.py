"""Database engine factory, session management, and schema creation.

Responsibilities
----------------
- Build an SQLAlchemy ``Engine`` from ``Settings.db_url``.
- Expose a ``SessionLocal`` factory and a ``get_db()`` dependency (FastAPI-style).
- Provide ``create_all_tables()`` and ``drop_all_tables()`` helpers.
- Support both real SQLite/PostgreSQL connections and an in-memory SQLite
  engine for unit tests (``make_test_engine()``).

Usage
-----
    from lakenterprises.db import get_db, create_all_tables

    # FastAPI dependency
    def my_route(db: Session = Depends(get_db)): ...

    # CLI / startup
    create_all_tables()
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from .config import get_settings
from .models import Base


# ---------------------------------------------------------------------------
# Engine construction
# ---------------------------------------------------------------------------


def make_engine(db_url: str | None = None, **kwargs) -> Engine:
    """Create an SQLAlchemy engine.

    Args:
        db_url: Override the URL from ``Settings``. Defaults to
                ``settings.db_url`` (SQLite at ``data/enterprise.db``).
        **kwargs: Extra keyword arguments forwarded to ``create_engine``.

    Returns:
        A configured ``Engine`` instance.
    """
    url = db_url or get_settings().db_url

    # SQLite-specific pragmas for safe concurrent access
    if url.startswith("sqlite"):
        connect_args = kwargs.pop("connect_args", {"check_same_thread": False})
        engine = create_engine(
            url,
            connect_args=connect_args,
            **kwargs,
        )
        # Enable WAL mode and foreign-key enforcement for every connection
        with engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.execute(text("PRAGMA foreign_keys=ON"))
        return engine

    return create_engine(url, **kwargs)


def make_test_engine() -> Engine:
    """Return an in-memory SQLite engine for unit tests.

    Uses ``StaticPool`` so the same in-memory DB is shared across all
    connections created by the test session factory.
    """
    return create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return a ``sessionmaker`` bound to the given engine."""
    return sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )


# ---------------------------------------------------------------------------
# Module-level singletons (lazy – not created until first use)
# ---------------------------------------------------------------------------

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def _get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = make_engine()
    return _engine


def _get_session_factory() -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = make_session_factory(_get_engine())
    return _SessionLocal


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def get_db() -> Generator[Session, None, None]:
    """Yield a database session and ensure it is closed afterwards.

    Designed for use as a FastAPI ``Depends`` dependency *or* inside a
    ``with`` statement in scripts / tests.

    Example::

        # As a FastAPI dependency
        def route(db: Session = Depends(get_db)):
            ...

        # As a context manager
        with contextlib.contextmanager(get_db)() as db:
            ...
    """
    db = _get_session_factory()()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def db_session() -> Generator[Session, None, None]:
    """Context-manager wrapper around ``get_db()`` for non-FastAPI callers."""
    yield from get_db()


def create_all_tables(engine: Engine | None = None) -> None:
    """Create all ORM-mapped tables (safe to call repeatedly: ``CREATE TABLE IF NOT EXISTS``)."""
    eng = engine or _get_engine()
    Base.metadata.create_all(bind=eng)


def drop_all_tables(engine: Engine | None = None) -> None:
    """Drop all ORM-mapped tables (destructive – for tests only)."""
    eng = engine or _get_engine()
    Base.metadata.drop_all(bind=eng)


def reset_engine(engine: Engine | None = None, session_factory: sessionmaker | None = None) -> None:
    """Replace the module-level engine and session factory (for testing)."""
    global _engine, _SessionLocal
    _engine = engine
    _SessionLocal = session_factory
