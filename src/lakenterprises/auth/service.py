"""Central authentication and authorization service.

Uses ``python-jose`` for JWT token management and ``passlib.bcrypt``
for password hashing (with ``pbkdf2_sha256`` as a fallback when bcrypt
is unavailable).  ORM models are lazy-imported so the service works
without a SQLAlchemy session.
"""

from __future__ import annotations

import datetime
import logging
from typing import Any

from jose import jwt
from jose.exceptions import ExpiredSignatureError, JWTError
from passlib.hash import bcrypt as bcrypt_hash
from passlib.hash import pbkdf2_sha256

from .exceptions import (InvalidCredentialsError, TokenExpiredError,
                         TokenRevokedError)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Optional SQLAlchemy support
# ---------------------------------------------------------------------------


def _get_user_model() -> type | None:
    """Lazy-load the User ORM model, if available."""
    try:
        from lakenterprises.models.entities import User  # noqa: F401

        return User  # type: ignore[return-value]
    except (ImportError, AttributeError):
        return None


def _get_auth_token_model() -> type | None:
    """Lazy-load the AuthToken ORM model, if available."""
    try:
        from lakenterprises.models.entities import AuthToken  # noqa: F401

        return AuthToken  # type: ignore[return-value]
    except (ImportError, AttributeError):
        return None


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class AuthService:
    """Central authentication and authorization service.

    Parameters
    ----------
    secret_key:
        Secret used to sign and verify JWT tokens.
    algorithm:
        Signing algorithm (default ``HS256``).
    access_token_expire_minutes:
        Lifetime of access tokens in minutes (default 30).
    refresh_token_expire_days:
        Lifetime of refresh tokens in days (default 7).
    """

    def __init__(
        self,
        secret_key: str,
        algorithm: str = "HS256",
        access_token_expire_minutes: int = 30,
        refresh_token_expire_days: int = 7,
    ) -> None:
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.access_token_expire_minutes = access_token_expire_minutes
        self.refresh_token_expire_days = refresh_token_expire_days
        self._user_model = _get_user_model()
        self._auth_token_model = _get_auth_token_model()
        self._revoked_tokens: set[str] = set()

    # ------------------------------------------------------------------
    # Password hashing
    # ------------------------------------------------------------------

    def hash_password(self, password: str) -> str:
        r"""Hash *password* using bcrypt (or pbkdf2_sha256 as fallback).

        Returns the hash string.
        """
        try:
            return bcrypt_hash.hash(password)
        except (ValueError, LookupError):
            return pbkdf2_sha256.hash(password)

    def verify_password(self, password: str, hash_str: str) -> bool:
        """Verify *password* against *hash_str*.

        Returns ``True`` when the password is correct, ``False``
        otherwise.
        """
        try:
            return bcrypt_hash.verify(password, hash_str)
        except (ValueError, LookupError):
            return pbkdf2_sha256.verify(password, hash_str)

    # ------------------------------------------------------------------
    # Token creation
    # ------------------------------------------------------------------

    def create_access_token(
        self,
        user_id: str,
        permissions: list[str] | None = None,
        extra_claims: dict[str, Any] | None = None,
    ) -> str:
        """Create a short-lived access JWT.

        The token contains claims: ``sub``, ``permissions``, ``exp``,
        ``iat``, and ``type`` (``"access"``).

        Returns the encoded token string.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        expire = now + datetime.timedelta(minutes=self.access_token_expire_minutes)

        payload: dict[str, Any] = {
            "sub": user_id,
            "permissions": permissions or [],
            "exp": expire,
            "iat": now,
            "type": "access",
        }
        if extra_claims:
            payload.update(extra_claims)

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def create_refresh_token(self, user_id: str) -> str:
        """Create a long-lived refresh JWT.

        The token contains claims: ``sub``, ``exp``, ``iat``, and
        ``type`` (``"refresh"``).

        Returns the encoded token string.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        expire = now + datetime.timedelta(days=self.refresh_token_expire_days)

        payload: dict[str, Any] = {
            "sub": user_id,
            "exp": expire,
            "iat": now,
            "type": "refresh",
        }

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    # ------------------------------------------------------------------
    # Token decoding
    # ------------------------------------------------------------------

    def decode_token(self, token: str) -> dict[str, Any]:
        """Decode and verify a JWT token.

        Returns the payload dict on success.

        Raises
        ------
        TokenExpiredError
            When the token has expired.
        TokenRevokedError
            When the token carries a ``"revoked"`` claim set to ``True``.
        AuthException (base)
            For other JWT errors (malformed, wrong signature, etc.).
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options={"verify_exp": True},
            )
        except ExpiredSignatureError:
            raise TokenExpiredError("Token has expired") from None
        except JWTError as exc:
            raise TokenRevokedError(f"Invalid token: {exc}") from None

        import hashlib

        token_hash = hashlib.sha256(token.encode()).hexdigest()
        if (
            token_hash in self._revoked_tokens
            or token in self._revoked_tokens
            or payload.get("revoked")
        ):
            raise TokenRevokedError("Token has been revoked")

        return payload

    # ------------------------------------------------------------------
    # Login / refresh
    # ------------------------------------------------------------------

    def login(
        self, email: str, password: str, db_session: Any
    ) -> tuple[str, str, dict[str, Any]]:
        """Authenticate a user by email and password.

        Parameters
        ----------
        email:
            User's email address.
        password:
            Plain-text password.
        db_session:
            A SQLAlchemy session (or compatible) used to look up the
            user and store token records.

        Returns
        -------
        (access_token, refresh_token, user_dict)

        Raises
        ------
        InvalidCredentialsError
            When the user is not found or the password is wrong.
        """
        User = self._user_model
        if User is None:
            raise InvalidCredentialsError(email, "User model not available")

        from sqlalchemy import select  # type: ignore[import-not-found]

        stmt = select(User).where(User.email == email)
        user = db_session.execute(stmt).scalar_one_or_none()

        if user is None:
            raise InvalidCredentialsError(email, "User not found")

        if not self.verify_password(password, user.password_hash):
            raise InvalidCredentialsError(email, "Invalid password")

        permissions: list[str] = getattr(user, "permissions", []) or []
        if isinstance(permissions, str):
            import json

            try:
                permissions = json.loads(permissions)
            except (json.JSONDecodeError, TypeError):
                permissions = []

        user_dict: dict[str, Any] = {
            "id": str(getattr(user, "id", "")),
            "email": getattr(user, "email", ""),
            "first_name": getattr(user, "first_name", ""),
            "last_name": getattr(user, "last_name", ""),
            "permissions": permissions,
            "roles": getattr(user, "roles", []) or [],
            "is_active": getattr(user, "is_active", True),
            "is_authenticated": True,
        }

        if isinstance(user_dict["roles"], str):
            import json

            try:
                user_dict["roles"] = json.loads(user_dict["roles"])
            except (json.JSONDecodeError, TypeError):
                user_dict["roles"] = []

        access_token = self.create_access_token(user_dict["id"], permissions)
        refresh_token = self.create_refresh_token(user_dict["id"])

        # Persist token record if model is available
        if self._auth_token_model is not None:
            self._store_token(
                db_session,
                user_dict["id"],
                access_token,
                refresh_token,
            )

        return access_token, refresh_token, user_dict

    def refresh(self, refresh_token: str, db_session: Any) -> tuple[str, str]:
        """Verify a refresh token and issue a new access + refresh pair.

        Parameters
        ----------
        refresh_token:
            The existing refresh JWT.
        db_session:
            A SQLAlchemy session used for token bookkeeping.

        Returns
        -------
        (new_access_token, new_refresh_token)

        Raises
        ------
        TokenExpiredError / TokenRevokedError
            When the refresh token is invalid, expired, or revoked.
        """
        payload = self.decode_token(refresh_token)

        if payload.get("type") != "refresh":
            raise TokenRevokedError("Not a refresh token")

        user_id = payload["sub"]

        # Revoke old refresh token in DB (best-effort)
        if self._auth_token_model is not None and db_session is not None:
            self._revoke_stored_token(db_session, refresh_token)

        permissions = payload.get("permissions", [])
        new_access = self.create_access_token(user_id, permissions)
        new_refresh = self.create_refresh_token(user_id)

        if self._auth_token_model is not None and db_session is not None:
            self._store_token(db_session, user_id, new_access, new_refresh)

        return new_access, new_refresh

    # ------------------------------------------------------------------
    # Permission / role checks
    # ------------------------------------------------------------------

    def check_permission(
        self, user_permissions: list[str], required_permission: str
    ) -> bool:
        """Return ``True`` if *required_permission* is in *user_permissions*."""
        return required_permission in user_permissions

    def check_role(self, user_roles: list[str], required_role: str) -> bool:
        """Return ``True`` if *required_role* is in *user_roles*."""
        return required_role in user_roles

    # ------------------------------------------------------------------
    # Token revocation
    # ------------------------------------------------------------------

    def revoke_token(self, token_hash: str, db_session: Any) -> bool:
        """Mark an ``AuthToken`` as revoked in the database.

        Parameters
        ----------
        token_hash:
            The token value (or its hash) to look up.
        db_session:
            A SQLAlchemy session.

        Returns
        -------
        ``True`` if the token was found and revoked, ``False`` otherwise.
        """
        self._revoked_tokens.add(token_hash)
        if self._auth_token_model is None or db_session is None:
            return False

        from sqlalchemy import select  # type: ignore[import-not-found]

        stmt = select(self._auth_token_model).where(
            self._auth_token_model.token_hash == token_hash
        )
        token_records = db_session.execute(stmt).scalars().all()

        if not token_records:
            return False

        for token_record in token_records:
            if hasattr(token_record, "is_revoked"):
                token_record.is_revoked = True
            if hasattr(token_record, "revoked"):
                token_record.revoked = True
        db_session.commit()
        return True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _store_token(
        self,
        db_session: Any,
        user_id: str,
        access_token: str,
        refresh_token: str,
    ) -> None:
        """Persist a new token pair to the database (best-effort)."""
        if self._auth_token_model is None or db_session is None:
            return

        import hashlib

        now = datetime.datetime.now(datetime.timezone.utc)
        try:
            acc_attrs: dict[str, Any] = {
                "user_id": user_id,
                "token_hash": hashlib.sha256(access_token.encode()).hexdigest(),
                "expires_at": now
                + datetime.timedelta(minutes=self.access_token_expire_minutes),
            }
            if hasattr(self._auth_token_model, "token"):
                acc_attrs["token"] = access_token
            if hasattr(self._auth_token_model, "token_type"):
                acc_attrs["token_type"] = "access"
            if hasattr(self._auth_token_model, "is_revoked"):
                acc_attrs["is_revoked"] = False
            db_session.add(self._auth_token_model(**acc_attrs))

            ref_attrs: dict[str, Any] = {
                "user_id": user_id,
                "token_hash": hashlib.sha256(refresh_token.encode()).hexdigest(),
                "expires_at": now
                + datetime.timedelta(days=self.refresh_token_expire_days),
            }
            if hasattr(self._auth_token_model, "token"):
                ref_attrs["token"] = refresh_token
            if hasattr(self._auth_token_model, "token_type"):
                ref_attrs["token_type"] = "refresh"
            if hasattr(self._auth_token_model, "is_revoked"):
                ref_attrs["is_revoked"] = False
            db_session.add(self._auth_token_model(**ref_attrs))
            db_session.commit()
        except Exception:
            logger.exception("Failed to store token record")
            try:
                db_session.rollback()
            except Exception:
                pass

    def _revoke_stored_token(self, db_session: Any, token: str) -> None:
        """Mark a stored token as revoked (best-effort)."""
        import hashlib

        token_hash = hashlib.sha256(token.encode()).hexdigest()
        self._revoked_tokens.add(token_hash)
        self._revoked_tokens.add(token)
        if self._auth_token_model is None or db_session is None:
            return

        try:
            from sqlalchemy import select  # type: ignore[import-not-found]

            stmt = select(self._auth_token_model).where(
                self._auth_token_model.token_hash == token_hash
            )
            record = db_session.execute(stmt).scalar_one_or_none()
            if record is not None:
                if hasattr(record, "is_revoked"):
                    record.is_revoked = True
                if hasattr(record, "revoked"):
                    record.revoked = True
                db_session.commit()
        except Exception:
            logger.exception("Failed to revoke stored token")
            try:
                db_session.rollback()
            except Exception:
                pass
