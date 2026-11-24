"""Tests for SessionService – in-memory session management."""

import datetime as dt
import importlib
import os
import sys
import tempfile

import pytest

# ---------------------------------------------------------------------------
# Fixtures – fresh temp SQLite DB + module reload per test
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _fresh_db(monkeypatch):
    """Reset cached engine/factory so each test gets its own temp SQLite DB."""
    # Clear any cached engine / session factory from prior tests
    db_mod = sys.modules.get("lakenterprises.db")
    if db_mod is not None:
        db_mod._engine = None
        db_mod._session_factory = None

    tmp = tempfile.mktemp()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp}")

    # Ensure config is imported first, then reload both modules
    from lakenterprises.config import Settings  # noqa: F401

    importlib.reload(sys.modules["lakenterprises.config"])
    if "lakenterprises.db" in sys.modules:
        importlib.reload(sys.modules["lakenterprises.db"])

    from lakenterprises.db import get_db_session, init_db

    init_db()
    session = get_db_session()
    yield session
    session.close()


@pytest.fixture
def manager(_fresh_db):
    from lakenterprises.services.session import SessionService

    return SessionService(db_session=_fresh_db)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_create_session_is_active(manager):
    rec = manager.create_session("user-1", ip_address="1.2.3.4")
    assert rec["active"] is True
    assert rec["user_id"] == "user-1"
    assert rec["ip_address"] == "1.2.3.4"


def test_create_session_expires_at(manager):
    rec = manager.create_session("user-1")
    expires = dt.datetime.fromisoformat(rec["expires_at"])
    created = dt.datetime.fromisoformat(rec["created_at"])
    delta = expires - created
    assert dt.timedelta(minutes=29) <= delta <= dt.timedelta(minutes=31)


def test_invalidate_session_returns_true(manager):
    rec = manager.create_session("user-1")
    assert manager.invalidate_session(rec["session_id"]) is True


def test_invalidate_session_removes_from_memory(manager):
    rec = manager.create_session("user-1")
    manager.invalidate_session(rec["session_id"])
    assert manager.get_session(rec["session_id"]) is None


def test_invalidate_nonexistent_returns_false(manager):
    assert manager.invalidate_session("no-such-id") is False


def test_invalidate_user_sessions_count(manager):
    manager.create_session("user-1")
    manager.create_session("user-1")
    manager.create_session("user-2")
    assert manager.invalidate_user_sessions("user-1") == 2
    assert manager.invalidate_user_sessions("user-2") == 1
    assert manager.invalidate_user_sessions("nobody") == 0


def test_get_active_sessions_only_active(manager):
    rec1 = manager.create_session("user-1")
    rec2 = manager.create_session("user-1")
    rec3 = manager.create_session("user-2")
    manager.invalidate_session(rec1["session_id"])
    active = manager.get_active_sessions("user-1")
    assert len(active) == 1
    assert active[0]["session_id"] == rec2["session_id"]


def test_get_session_returns_session_or_none(manager):
    rec = manager.create_session("user-1")
    found = manager.get_session(rec["session_id"])
    assert found is not None
    assert found["user_id"] == "user-1"
    assert manager.get_session("missing") is None
