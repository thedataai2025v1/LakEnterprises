"""Unit tests for lakenterprises.auth.service.AuthService."""

import datetime
import hashlib
import os
import sys
import tempfile

import jwt
import pytest

# Ensure src/ is on sys.path so package imports work from the tests dir.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from lakenterprises.auth.exceptions import TokenExpiredError, TokenRevokedError
from lakenterprises.auth.service import AuthService

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def service():
    return AuthService(secret_key="test-secret-key")


@pytest.fixture
def db_session():
    """Create a temporary SQLite DB and yield a session."""
    os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mktemp()}"
    from lakenterprises.db import get_db_session, init_db

    init_db()
    session = get_db_session()
    yield session
    session.close()


# ---------------------------------------------------------------------------
# 1. hash_password returns different hashes for the same password
# ---------------------------------------------------------------------------


class TestHashPassword:
    def test_different_hashes(self, service):
        pw = "my-secret-password"
        h1 = service.hash_password(pw)
        h2 = service.hash_password(pw)
        assert h1 != h2
        assert len(h1) == 60
        assert len(h2) == 60


# ---------------------------------------------------------------------------
# 2. verify_password works with correct / incorrect passwords
# ---------------------------------------------------------------------------


class TestVerifyPassword:
    def test_correct(self, service):
        pw = "correct"
        hashed = service.hash_password(pw)
        assert service.verify_password(pw, hashed) is True

    def test_incorrect(self, service):
        pw = "correct"
        hashed = service.hash_password(pw)
        assert service.verify_password("wrong", hashed) is False

    def test_empty_password(self, service):
        hashed = service.hash_password("")
        assert service.verify_password("", hashed) is True
        assert service.verify_password("x", hashed) is False


# ---------------------------------------------------------------------------
# 3. create_access_token returns a valid JWT
# ---------------------------------------------------------------------------


class TestCreateAccessToken:
    def test_returns_string(self, service):
        token = service.create_access_token("user-1")
        assert isinstance(token, str)
        assert len(token) > 20

    def test_contains_claims(self, service):
        token = service.create_access_token("user-1", permissions=["read", "write"])
        payload = service.decode_token(token)
        assert payload["sub"] == "user-1"
        assert payload["permissions"] == ["read", "write"]
        assert "exp" in payload


# ---------------------------------------------------------------------------
# 4. decode_token decodes correctly and extracts sub / exp
# ---------------------------------------------------------------------------


class TestDecodeToken:
    def test_sub_and_exp(self, service):
        token = service.create_access_token("u-42")
        payload = service.decode_token(token)
        assert payload["sub"] == "u-42"
        assert isinstance(payload["exp"], (int, float))

    def test_type_claim(self, service):
        token = service.create_access_token("u-99")
        payload = service.decode_token(token)
        assert payload.get("type") == "access"


# ---------------------------------------------------------------------------
# 5. decode_token raises on expired tokens
# ---------------------------------------------------------------------------


class TestExpiredToken:
    def test_raises_on_expired(self, service):
        now = datetime.datetime.now(datetime.timezone.utc)
        payload = {
            "sub": "user-1",
            "exp": now - datetime.timedelta(seconds=1),
        }
        token = jwt.encode(payload, service.secret_key, algorithm=service.algorithm)
        with pytest.raises(TokenExpiredError):
            service.decode_token(token)


# ---------------------------------------------------------------------------
# 6. decode_token raises on tampered tokens
# ---------------------------------------------------------------------------


class TestTamperedToken:
    def test_raises_on_tampered(self, service):
        token = service.create_access_token("user-1")
        tampered = token + "x"
        with pytest.raises(TokenRevokedError):
            service.decode_token(tampered)

    def test_raises_on_wrong_key(self, service):
        token = service.create_access_token("user-1")
        other = AuthService(secret_key="different-key")
        with pytest.raises(TokenRevokedError):
            other.decode_token(token)


# ---------------------------------------------------------------------------
# 7. refresh returns a new access token
# ---------------------------------------------------------------------------


class TestRefresh:
    def test_returns_new_access_token(self, service, db_session):
        """refresh() creates a new access token while reusing the refresh token."""
        refresh_tok = service.create_refresh_token("user-1")

        new_access, new_refresh = service.refresh(refresh_tok, db_session)
        assert new_access is not None
        assert new_refresh is not None

        payload = service.decode_token(new_access)
        assert payload["sub"] == "user-1"
        assert "exp" in payload


# ---------------------------------------------------------------------------
# 8. revoke invalidates old token
# ---------------------------------------------------------------------------


class TestRevoke:
    def test_revoke_invalidates_token(self, service, db_session):
        """Store a token hash directly in the AuthToken model, revoke it,
        then confirm decode_token raises TokenRevokedError."""
        access_token = service.create_access_token("user-1")
        token_hash = hashlib.sha256(access_token.encode()).hexdigest()

        from lakenterprises.models.entities import AuthToken

        # Insert the token hash using the real columns
        auth_record = AuthToken(
            user_id="user-1",
            token_hash=token_hash,
            refresh_token_hash="dummy-refresh-hash",
            is_revoked=False,
        )
        db_session.add(auth_record)
        db_session.commit()

        # Revoke
        assert service.revoke_token(token_hash, db_session) is True

        # decode_token checks revoked hashes and must raise
        with pytest.raises(TokenRevokedError):
            service.decode_token(access_token)

    def test_revoke_nonexistent(self, service, db_session):
        result = service.revoke_token("does-not-exist", db_session)
        assert result is False
