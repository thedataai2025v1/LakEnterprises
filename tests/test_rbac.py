"""Tests for RBAC decorators and auth exceptions.

Tests cover the actual implementations in:
  src/lakenterprises/auth/middleware.py
  src/lakenterprises/auth/exceptions.py
"""

import pytest

from lakenterprises.auth.exceptions import (AuthException,
                                            InsufficientPermissionsError,
                                            InvalidCredentialsError,
                                            SessionExpiredError,
                                            TokenExpiredError,
                                            TokenRevokedError)
from lakenterprises.auth.middleware import (admin_only, require_auth,
                                            require_permission)

# -- Test users (dict-based, matching middleware expectations) ----------------
ADMIN_USER = {
    "id": "admin-1",
    "is_authenticated": True,
    "roles": ["ADMIN"],
    "permissions": ["ADMIN_ACCESS", "VIEW_DASHBOARD"],
}

EDITOR_USER = {
    "id": "editor-1",
    "is_authenticated": True,
    "roles": ["EDITOR"],
    "permissions": ["VIEW_DASHBOARD"],
}

UNAUTHENTICATED_USER = {
    "id": "guest-1",
    "is_authenticated": False,
    "roles": [],
    "permissions": [],
}


# -- require_auth ------------------------------------------------------------
class TestRequireAuth:
    def test_passes_for_authenticated_user(self):
        @require_auth
        def handler(*, current_user, **kw):
            return "ok"

        result = handler(current_user=ADMIN_USER)
        assert result == "ok"

    def test_raises_for_unauthenticated_user(self):
        @require_auth
        def handler(*, current_user, **kw):
            return "ok"

        with pytest.raises(InsufficientPermissionsError) as exc:
            handler(current_user=UNAUTHENTICATED_USER)
        assert "Authentication required" in str(exc.value)

    def test_raises_when_no_user(self):
        @require_auth
        def handler(*, current_user, **kw):
            return "ok"

        with pytest.raises(InsufficientPermissionsError):
            handler(current_user=None)

    def test_raises_when_empty_user(self):
        @require_auth
        def handler(*, current_user, **kw):
            return "ok"

        with pytest.raises(InsufficientPermissionsError):
            handler(current_user={})


# -- require_permission -------------------------------------------------------
class TestRequirePermission:
    def test_passes_when_user_has_permission(self):
        @require_permission("VIEW_DASHBOARD")
        def handler(*, current_user, **kw):
            return "ok"

        result = handler(current_user=EDITOR_USER)
        assert result == "ok"

    def test_raises_when_user_lacks_permission(self):
        @require_permission("ADMIN_ACCESS")
        def handler(*, current_user, **kw):
            return "ok"

        with pytest.raises(InsufficientPermissionsError) as exc:
            handler(current_user=EDITOR_USER)
        assert "ADMIN_ACCESS" in str(exc.value)

    def test_raises_when_no_user(self):
        @require_permission("VIEW_DASHBOARD")
        def handler(*, current_user, **kw):
            return "ok"

        with pytest.raises(InsufficientPermissionsError) as exc:
            handler(current_user=None)
        assert "Permission required" in str(exc.value)


# -- admin_only (require_admin) -----------------------------------------------
class TestAdminOnly:
    def test_passes_for_admin(self):
        @admin_only
        def handler(*, current_user, **kw):
            return "ok"

        result = handler(current_user=ADMIN_USER)
        assert result == "ok"

    def test_raises_for_non_admin(self):
        @admin_only
        def handler(*, current_user, **kw):
            return "ok"

        with pytest.raises(InsufficientPermissionsError) as exc:
            handler(current_user=EDITOR_USER)
        assert "Admin role required" in str(exc.value)

    def test_raises_when_no_user(self):
        @admin_only
        def handler(*, current_user, **kw):
            return "ok"

        with pytest.raises(InsufficientPermissionsError) as exc:
            handler(current_user=None)
        assert "Admin access required" in str(exc.value)


# -- Exception messages & attributes ------------------------------------------
class TestAuthExceptions:
    def test_auth_exception_base(self):
        e = AuthException("generic auth error")
        assert "generic auth error" in str(e)

    def test_invalid_credentials_error(self):
        e = InvalidCredentialsError("user123", "wrong password")
        assert e.identifier == "user123"
        assert e.message == "wrong password"
        assert "wrong password" in str(e)

    def test_token_expired_error(self):
        e = TokenExpiredError("expired 1h ago")
        assert "expired 1h ago" in str(e)

    def test_token_revoked_error(self):
        e = TokenRevokedError()
        assert "Token has been revoked" in str(e)

    def test_insufficient_permissions_error(self):
        e = InsufficientPermissionsError("need ADMIN_ACCESS", user_id="u1")
        assert e.user_id == "u1"
        assert e.permission_name == "need ADMIN_ACCESS"
        assert "ADMIN_ACCESS" in str(e)

    def test_session_expired_error(self):
        e = SessionExpiredError()
        assert "Session has expired" in str(e)

    def test_insufficient_permissions_default_user_id(self):
        e = InsufficientPermissionsError("no role")
        assert e.user_id is None
