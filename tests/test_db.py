"""Integration tests for P2-2: DB module (engine factory and session management)."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from lakenterprises.db import (
    create_all_tables,
    db_session,
    drop_all_tables,
    make_engine,
    make_session_factory,
    make_test_engine,
    reset_engine,
)
from lakenterprises.models import Base, User


class TestMakeTestEngine:
    def test_creates_engine(self):
        eng = make_test_engine()
        assert eng is not None
        eng.dispose()

    def test_in_memory_sqlite(self):
        eng = make_test_engine()
        assert "sqlite" in str(eng.url)
        eng.dispose()

    def test_tables_creatable(self):
        eng = make_test_engine()
        create_all_tables(eng)
        from sqlalchemy import inspect
        tables = inspect(eng).get_table_names()
        assert "users" in tables
        eng.dispose()


class TestMakeEngine:
    def test_sqlite_file_url(self, tmp_path):
        db_file = tmp_path / "test.db"
        eng = make_engine(f"sqlite:///{db_file}")
        create_all_tables(eng)
        assert db_file.exists()
        eng.dispose()

    def test_sqlite_pragmas_applied(self, tmp_path):
        db_file = tmp_path / "pragma.db"
        eng = make_engine(f"sqlite:///{db_file}")
        with eng.connect() as conn:
            result = conn.execute(text("PRAGMA journal_mode"))
            mode = result.fetchone()[0]
        assert mode == "wal"
        eng.dispose()


class TestSessionFactory:
    def test_session_creation(self):
        eng = make_test_engine()
        create_all_tables(eng)
        factory = make_session_factory(eng)
        session = factory()
        assert isinstance(session, Session)
        session.close()
        eng.dispose()

    def test_session_commit_and_rollback(self):
        eng = make_test_engine()
        create_all_tables(eng)
        factory = make_session_factory(eng)
        session = factory()

        user = User(email="test@db.com", full_name="DB User", hashed_password="h")
        session.add(user)
        session.commit()
        assert user.id is not None

        # Verify persisted
        session.expunge_all()
        fetched = session.get(User, user.id)
        assert fetched is not None

        session.close()
        eng.dispose()

    def test_rollback_on_exception(self):
        eng = make_test_engine()
        create_all_tables(eng)
        factory = make_session_factory(eng)
        session = factory()

        try:
            user = User(email="rollback@db.com", full_name="Rollback", hashed_password="h")
            session.add(user)
            session.flush()
            raise RuntimeError("Simulated error")
        except RuntimeError:
            session.rollback()

        # Row should not be committed
        from sqlalchemy import select
        result = session.execute(select(User).where(User.email == "rollback@db.com"))
        assert result.first() is None

        session.close()
        eng.dispose()


class TestDbSessionContextManager:
    def test_db_session_yields_session(self):
        eng = make_test_engine()
        create_all_tables(eng)
        factory = make_session_factory(eng)

        # Temporarily override the module-level engine
        reset_engine(eng, factory)

        with db_session() as db:
            assert isinstance(db, Session)
            user = User(email="ctx@test.com", full_name="CTX", hashed_password="h")
            db.add(user)
            db.flush()
            assert user.id is not None

        # Clean up
        reset_engine(None, None)
        eng.dispose()


class TestCreateDropAllTables:
    def test_drop_and_recreate(self):
        eng = make_test_engine()
        create_all_tables(eng)
        from sqlalchemy import inspect
        assert "users" in inspect(eng).get_table_names()

        drop_all_tables(eng)
        assert "users" not in inspect(eng).get_table_names()

        create_all_tables(eng)
        assert "users" in inspect(eng).get_table_names()

        eng.dispose()
