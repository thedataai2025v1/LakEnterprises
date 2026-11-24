"""Tests for all repository classes in src/lakenterprises/repositories.py."""

import os
import sys
import tempfile
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mktemp()}"
from lakenterprises.db import get_db_session, init_db, reset_db  # noqa: E402

init_db()


@pytest.fixture(autouse=True)
def db():
    reset_db()
    session = get_db_session()
    yield session
    session.close()


# ====================================================================
# UserRepository
# ====================================================================
class TestUserRepository:
    def _repo(self, db):
        from lakenterprises.repositories import UserRepository

        return UserRepository(db)

    def test_create_and_get_by_id(self, db):
        repo = self._repo(db)
        u = repo.create(
            username="alice", email="alice@example.com", password_hash="pw123"
        )
        found = repo.get_by_id(u.id)
        assert found is not None
        assert found.username == "alice"
        assert found.email == "alice@example.com"
        assert found.is_active is True
        assert found.is_verified is False

    def test_get_by_username_and_email(self, db):
        repo = self._repo(db)
        u = repo.create(username="bob", email="bob@x.com", password_hash="h")
        assert repo.get_by_username("bob").id == u.id
        assert repo.get_by_email("bob@x.com").id == u.id

    def test_get_by_nonexistent(self, db):
        repo = self._repo(db)
        assert repo.get_by_username("nobody") is None
        assert repo.get_by_email("no@x.com") is None
        assert repo.get_by_id("no-such-id") is None

    def test_get_all(self, db):
        repo = self._repo(db)
        repo.create(username="u1", email="1@x.com", password_hash="h")
        repo.create(username="u2", email="2@x.com", password_hash="h")
        assert len(repo.get_all()) == 2

    def test_get_active(self, db):
        repo = self._repo(db)
        u1 = repo.create(
            username="active1", email="a1@x.com", password_hash="h", is_active=True
        )
        u2 = repo.create(
            username="active2", email="a2@x.com", password_hash="h", is_active=True
        )
        repo.create(
            username="inactive1", email="i1@x.com", password_hash="h", is_active=False
        )
        assert len(repo.get_active()) == 2

    def test_search(self, db):
        repo = self._repo(db)
        repo.create(
            username="alice",
            email="alice@example.com",
            password_hash="h",
            first_name="Alice",
        )
        repo.create(
            username="bob", email="bob@example.com", password_hash="h", first_name="Bob"
        )
        results = repo.search("alice")
        assert any(r.username == "alice" for r in results)
        assert not any(r.username == "bob" for r in results)

    def test_create_with_roles(self, db):
        repo = self._repo(db)
        from lakenterprises.repositories import RoleRepository

        role_repo = RoleRepository(db)
        role = role_repo.create(name="admin", description="admins")
        u = repo.create(
            username="admin1", email="admin@x.com", password_hash="h", roles=[role]
        )
        assert len(u.roles) == 1
        assert u.roles[0].name == "admin"


# ====================================================================
# RoleRepository
# ====================================================================
class TestRoleRepository:
    def _repo(self, db):
        from lakenterprises.repositories import RoleRepository

        return RoleRepository(db)

    def test_create_and_get_by_id(self, db):
        repo = self._repo(db)
        r = repo.create(name="admin", description="admins")
        assert repo.get_by_id(r.id).name == "admin"

    def test_get_by_name(self, db):
        repo = self._repo(db)
        repo.create(name="editor", description="editors")
        assert repo.get_by_name("editor").name == "editor"

    def test_get_by_nonexistent(self, db):
        repo = self._repo(db)
        assert repo.get_by_name("ghost") is None
        assert repo.get_by_id("nope") is None

    def test_get_all(self, db):
        repo = self._repo(db)
        repo.create(name="r1", description="d")
        repo.create(name="r2", description="d")
        assert len(repo.get_all()) == 2

    def test_update(self, db):
        repo = self._repo(db)
        r = repo.create(name="old_name", description="desc")
        r = repo.update(r.id, name="new_name", description="updated")
        assert r.name == "new_name"
        assert r.description == "updated"

    def test_update_nonexistent(self, db):
        repo = self._repo(db)
        assert repo.update("no-id", name="x") is None


# ====================================================================
# PermissionRepository
# ====================================================================
class TestPermissionRepository:
    def _repo(self, db):
        from lakenterprises.repositories import PermissionRepository

        return PermissionRepository(db)

    def test_create_and_get(self, db):
        repo = self._repo(db)
        p = repo.create(name="read", description="read access")
        assert repo.get_by_id(p.id).name == "read"
        assert repo.get_by_name("read").id == p.id

    def test_get_by_nonexistent(self, db):
        repo = self._repo(db)
        assert repo.get_by_name("none") is None
        assert repo.get_by_id("xx") is None

    def test_get_all(self, db):
        repo = self._repo(db)
        repo.create(name="p1", description="d")
        repo.create(name="p2", description="d")
        assert len(repo.get_all()) == 2

    def test_update(self, db):
        repo = self._repo(db)
        p = repo.create(name="old", description="d")
        p = repo.update(p.id, name="new", description="changed")
        assert p.name == "new"
        assert p.description == "changed"

    def test_update_nonexistent(self, db):
        repo = self._repo(db)
        assert repo.update("no-id", name="x") is None


# ====================================================================
# AuthTokenRepository
# ====================================================================
class TestAuthTokenRepository:
    def _repo(self, db):
        from lakenterprises.repositories import AuthTokenRepository

        return AuthTokenRepository(db)

    def _future_dt(self):
        return datetime.now() + timedelta(hours=1)

    def test_create_and_get_by_id(self, db):
        repo = self._repo(db)
        t = repo.create(
            user_id="u1",
            token_hash="abc",
            refresh_token_hash="def",
            expires_at=self._future_dt(),
        )
        assert repo.get_by_id(t.id).user_id == "u1"
        assert t.is_revoked is False

    def test_get_by_token(self, db):
        repo = self._repo(db)
        repo.create(
            user_id="u1",
            token_hash="unique_hash",
            refresh_token_hash="r",
            expires_at=self._future_dt(),
        )
        assert repo.get_by_token("unique_hash").user_id == "u1"
        assert repo.get_by_token("missing") is None

    def test_get_all(self, db):
        repo = self._repo(db)
        repo.create(
            user_id="u1",
            token_hash="a",
            refresh_token_hash="r",
            expires_at=self._future_dt(),
        )
        repo.create(
            user_id="u2",
            token_hash="b",
            refresh_token_hash="r",
            expires_at=self._future_dt(),
        )
        assert len(repo.get_all()) == 2

    def test_revoke_by_id(self, db):
        repo = self._repo(db)
        t = repo.create(
            user_id="u1",
            token_hash="a",
            refresh_token_hash="r",
            expires_at=self._future_dt(),
        )
        assert repo.revoke_by_id(t.id) is True
        assert repo.get_by_id(t.id).is_revoked is True
        assert repo.revoke_by_id("bad-id") is False

    def test_revoke_all_for_user(self, db):
        repo = self._repo(db)
        repo.create(
            user_id="u1",
            token_hash="a",
            refresh_token_hash="r",
            expires_at=self._future_dt(),
        )
        repo.create(
            user_id="u1",
            token_hash="b",
            refresh_token_hash="r",
            expires_at=self._future_dt(),
        )
        repo.create(
            user_id="u2",
            token_hash="c",
            refresh_token_hash="r",
            expires_at=self._future_dt(),
        )
        assert repo.revoke_all_for_user("u1") == 2


# ====================================================================
# DocumentChunkRepository
# ====================================================================
class TestDocumentChunkRepository:
    def _repo(self, db):
        from lakenterprises.repositories import DocumentChunkRepository

        return DocumentChunkRepository(db)

    def test_create_and_get(self, db):
        repo = self._repo(db)
        c = repo.create(
            document_id="d1", chunk_index=0, content="hello world", embedding=None
        )
        assert repo.get_by_id(c.id).document_id == "d1"
        assert c.content == "hello world"
        assert c.word_count == 2

    def test_get_by_document_id(self, db):
        repo = self._repo(db)
        repo.create(document_id="d1", chunk_index=0, content="part1")
        repo.create(document_id="d1", chunk_index=1, content="part2")
        repo.create(document_id="d2", chunk_index=0, content="other")
        chunks = repo.get_by_document_id("d1")
        assert len(chunks) == 2
        assert chunks[0].chunk_index == 0
        assert chunks[1].chunk_index == 1

    def test_get_all(self, db):
        repo = self._repo(db)
        repo.create(document_id="d1", chunk_index=0, content="a")
        repo.create(document_id="d2", chunk_index=0, content="b")
        assert len(repo.get_all()) == 2

    def test_search(self, db):
        repo = self._repo(db)
        repo.create(document_id="d1", chunk_index=0, content="hello world")
        repo.create(document_id="d2", chunk_index=0, content="goodbye")
        results = repo.search("hello")
        assert len(results) == 1


# ====================================================================
# AuditLogRepository
# ====================================================================
class TestAuditLogRepository:
    def _repo(self, db):
        from lakenterprises.repositories import AuditLogRepository

        return AuditLogRepository(db)

    def test_create_and_get_by_id(self, db):
        repo = self._repo(db)
        a = repo.create(
            action="login",
            user_id="u1",
            entity_type="User",
            entity_id="u1",
            details={"msg": "ok"},
            severity="INFO",
        )
        assert repo.get_by_id(a.id).action == "login"

    def test_get_by_user_id(self, db):
        repo = self._repo(db)
        repo.create(action="login", user_id="u1")
        repo.create(action="view", user_id="u1")
        repo.create(action="delete", user_id="u2")
        assert len(repo.get_by_user_id("u1")) == 2
        assert len(repo.get_by_user_id("u2")) == 1

    def test_get_by_action(self, db):
        repo = self._repo(db)
        repo.create(action="login", user_id="u1")
        repo.create(action="logout", user_id="u1")
        assert len(repo.get_by_action("login")) == 1

    def test_get_by_severity(self, db):
        repo = self._repo(db)
        repo.create(action="login", severity="INFO")
        repo.create(action="hack", severity="ERROR")
        assert len(repo.get_by_severity("INFO")) == 1
        assert len(repo.get_by_severity("ERROR")) == 1

    def test_get_all(self, db):
        repo = self._repo(db)
        repo.create(action="a1")
        repo.create(action="a2")
        assert len(repo.get_all()) == 2


# ====================================================================
# SessionRecordRepository
# ====================================================================
class TestSessionRecordRepository:
    def _repo(self, db):
        from lakenterprises.repositories import SessionRecordRepository

        return SessionRecordRepository(db)

    def _future_dt(self):
        return datetime.now() + timedelta(hours=1)

    def test_create_and_get_by_id(self, db):
        repo = self._repo(db)
        t = repo.create(
            user_id="u1",
            session_id="s1",
            token_hash="abc",
            expires_at=self._future_dt(),
        )
        assert repo.get_by_id(t.id).user_id == "u1"

    def test_get_by_session_id(self, db):
        repo = self._repo(db)
        repo.create(
            user_id="u1",
            session_id="sess_1",
            token_hash="abc",
            expires_at=self._future_dt(),
        )
        found = repo.get_by_session_id("sess_1")
        assert found is not None
        assert found.user_id == "u1"
        assert repo.get_by_session_id("missing") is None

    def test_get_active_for_user(self, db):
        repo = self._repo(db)
        repo.create(
            user_id="u1", session_id="s1", token_hash="a", expires_at=self._future_dt()
        )
        repo.create(
            user_id="u1", session_id="s2", token_hash="b", expires_at=self._future_dt()
        )
        repo.create(
            user_id="u2", session_id="s3", token_hash="c", expires_at=self._future_dt()
        )
        active = repo.get_active_for_user("u1")
        assert len(active) == 2

    def test_get_all_active(self, db):
        repo = self._repo(db)
        repo.create(
            user_id="u1", session_id="s1", token_hash="a", expires_at=self._future_dt()
        )
        repo.create(
            user_id="u2", session_id="s2", token_hash="b", expires_at=self._future_dt()
        )
        assert len(repo.get_all_active()) == 2
