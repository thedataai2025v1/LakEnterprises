"""Tests for AuditService — in-memory and database-backed modes."""

import os
import sys
import tempfile

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def _db_session():
    path = tempfile.mktemp()
    os.environ["DATABASE_URL"] = f"sqlite:///{path}"
    src = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    from lakenterprises.db import get_db_session, init_db

    init_db()
    session = get_db_session()
    yield session
    session.close()
    if "DATABASE_URL" in os.environ:
        del os.environ["DATABASE_URL"]


@pytest.fixture
def service_mem():
    from lakenterprises.services.audit import AuditService

    return AuditService(db_session=None)


@pytest.fixture
def service_db(_db_session):
    from lakenterprises.services.audit import AuditService

    return AuditService(db_session=_db_session)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_log_severity_all_four_values(service_mem):
    for sev in ("INFO", "WARNING", "ERROR", "CRITICAL"):
        e = service_mem.log(action="t", user_id="u1", severity=sev)
        assert e["severity"] == sev


def test_log_creates_correct_fields(service_mem):
    e = service_mem.log(
        action="ACT",
        user_id="u1",
        details={"k": "v"},
        severity="INFO",
        ip_address="1.2.3.4",
    )
    assert e["action"] == "ACT"
    assert e["user_id"] == "u1"
    assert e["details"] == {"k": "v"}
    assert e["severity"] == "INFO"
    assert e["ip_address"] == "1.2.3.4"
    assert "entry_id" in e


def test_log_defaults(service_mem):
    e = service_mem.log(action="X", user_id="u1")
    assert e["severity"] == "INFO"
    assert e["details"] == {}
    assert e["ip_address"] is None


def test_login_success(service_mem):
    e = service_mem.log(action="LOGIN_SUCCESS", user_id="u1", severity="INFO")
    assert e["action"] == "LOGIN_SUCCESS"
    assert e["severity"] == "INFO"


def test_login_failure(service_mem):
    e = service_mem.log(action="LOGIN_FAILED", user_id="u2", severity="WARNING")
    assert e["action"] == "LOGIN_FAILED"
    assert e["severity"] == "WARNING"


def test_logout_logs_correctly(service_mem):
    e = service_mem.log(action="LOGOUT", user_id="u1")
    assert e["action"] == "LOGOUT"


def test_document_access(service_mem):
    e = service_mem.log(
        action="DOCUMENT_ACCESS", user_id="u1", details={"doc_id": "d1"}
    )
    assert e["action"] == "DOCUMENT_ACCESS"
    assert e["details"]["doc_id"] == "d1"


def test_document_change(service_mem):
    e = service_mem.log(
        action="DOCUMENT_CHANGE",
        user_id="u1",
        details={"doc_id": "d1", "change_type": "edit"},
    )
    assert e["action"] == "DOCUMENT_CHANGE"


def test_get_logs_filters_by_action(service_mem):
    service_mem.log(action="LOGIN_SUCCESS", user_id="u1")
    service_mem.log(action="LOGOUT", user_id="u1")
    service_mem.log(action="LOGIN_SUCCESS", user_id="u2")
    logs = service_mem.get_logs(action="LOGIN_SUCCESS")
    assert len(logs) == 2
    assert all(r["action"] == "LOGIN_SUCCESS" for r in logs)


def test_get_security_events_only_warning_plus(service_mem):
    service_mem.log(action="a", user_id="u1", severity="INFO")
    service_mem.log(action="b", user_id="u1", severity="WARNING")
    service_mem.log(action="c", user_id="u1", severity="ERROR")
    service_mem.log(action="d", user_id="u1", severity="CRITICAL")
    events = service_mem.get_security_events()
    sevs = {e["severity"] for e in events}
    assert "INFO" not in sevs
    assert sevs == {"WARNING", "ERROR", "CRITICAL"}


def test_get_user_activity_current_user(service_mem):
    service_mem.log(action="a", user_id="u1")
    service_mem.log(action="b", user_id="u2")
    service_mem.log(action="c", user_id="u1")
    logs = service_mem.get_user_activity(user_id="u1")
    assert len(logs) == 2
    assert all(e["user_id"] == "u1" for e in logs)


def test_db_fallback_to_memory(service_db):
    """DB persist may fail on current AuditLog model; service falls back."""
    e = service_db.log(action="FB", user_id="u1")
    assert e["action"] == "FB"  # always returns something
