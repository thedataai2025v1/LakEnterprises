"""Session management service.

Manages user sessions with an in-memory store (suitable for testing and
single-node deployments).  When ``db_session`` is provided it also
persists to / queries from the database via the ``AuthToken`` ORM model
(lazy-imported so the service is usable without SQLAlchemy).
"""

from __future__ import annotations

import datetime
import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Optional SQLAlchemy support
# ---------------------------------------------------------------------------


def _get_auth_token_model() -> type | None:
    """Lazy-load the AuthToken ORM model, if available."""
    try:
        from lakenterprises.models.entities import \
            AuthToken  # type: ignore[import-not-found, no-redef]

        return AuthToken
    except Exception:  # noqa: S110
        return None


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class SessionService:
    """Service for managing user sessions (in-memory + DB-backed).

    Parameters
    ----------
    db_session:
        A SQLAlchemy session (or None for in-memory-only mode).
    default_timeout_minutes:
        How long a session is valid before it expires, in minutes.
    """

    def __init__(
        self, db_session: Any = None, default_timeout_minutes: int = 30
    ) -> None:
        self._db_session = db_session
        self._sessions: dict[str, dict[str, Any]] = {}
        self.default_timeout = datetime.timedelta(minutes=default_timeout_minutes)
        self._model = _get_auth_token_model()

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def create_session(
        self,
        user_id: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        """Create a new session for *user_id*.

        Returns a dict with keys: ``session_id``, ``user_id``,
        ``expires_at``, ``created_at``, ``ip_address``, ``user_agent``,
        ``active``.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        session_id = str(uuid.uuid4())

        session: dict[str, Any] = {
            "session_id": session_id,
            "user_id": user_id,
            "expires_at": (now + self.default_timeout).isoformat(),
            "created_at": now.isoformat(),
            "ip_address": ip_address,
            "user_agent": user_agent,
            "active": True,
            "revoked": False,
        }

        # Store in-memory
        self._sessions[session_id] = session

        # Persist to DB if available
        if self._db_session is not None and self._model is not None:
            try:
                db_entry = self._model(
                    session_id=session_id,
                    user_id=user_id,
                    expires_at=now + self.default_timeout,
                    created_at=now,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    revoked=False,
                )
                self._db_session.add(db_entry)
                self._db_session.commit()
            except Exception:
                logger.exception("Failed to persist session to database")
                try:
                    self._db_session.rollback()
                except Exception:
                    pass

        return session

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Look up a session by ID.

        Returns None if the session does not exist or has expired.
        Expired sessions are removed from the in-memory store.
        """
        session = self._sessions.get(session_id)
        if session is None:
            return None

        if self._is_expired(session):
            self._remove_from_memory(session_id)
            return None

        if not session.get("active", True) or session.get("revoked", False):
            return None

        return dict(session)

    def refresh_session(self, session_id: str) -> dict[str, Any] | None:
        """Extend the session expiry by *default_timeout* from now.

        Returns the updated session dict or None if the session is not
        found, expired, or revoked.
        """
        session = self._sessions.get(session_id)
        if session is None:
            return None

        if self._is_expired(session):
            self._remove_from_memory(session_id)
            return None

        if not session.get("active", True) or session.get("revoked", False):
            return None

        now = datetime.datetime.now(datetime.timezone.utc)
        session["expires_at"] = (now + self.default_timeout).isoformat()

        # Update DB record
        if self._db_session is not None and self._model is not None:
            try:
                from sqlalchemy import select  # type: ignore[import-not-found]

                stmt = select(self._model).where(self._model.session_id == session_id)
                row = self._db_session.execute(stmt).scalar_one_or_none()
                if row is not None:
                    row.expires_at = now + self.default_timeout
                    self._db_session.commit()
            except Exception:
                logger.exception("Failed to refresh session in database")
                try:
                    self._db_session.rollback()
                except Exception:
                    pass

        return dict(session)

    def invalidate_session(self, session_id: str) -> bool:
        """Remove a session from memory and mark it revoked in the DB.

        Returns True if the session existed.
        """
        session = self._sessions.get(session_id)
        if session is None:
            return False

        self._remove_from_memory(session_id)
        session["active"] = False
        session["revoked"] = True

        # Mark revoked in DB
        if self._db_session is not None and self._model is not None:
            try:
                from sqlalchemy import select  # type: ignore[import-not-found]

                stmt = select(self._model).where(self._model.session_id == session_id)
                row = self._db_session.execute(stmt).scalar_one_or_none()
                if row is not None:
                    row.revoked = True
                    self._db_session.commit()
            except Exception:
                logger.exception("Failed to revoke session in database")
                try:
                    self._db_session.rollback()
                except Exception:
                    pass

        return True

    def invalidate_user_sessions(self, user_id: str) -> int:
        """Invalidate all sessions for a user.

        Returns the count of sessions invalidated.
        """
        if not user_id:
            return 0

        session_ids = [
            sid
            for sid, sess in self._sessions.items()
            if sess.get("user_id") == user_id
        ]

        for sid in session_ids:
            self._remove_from_memory(sid)

        # Revoke in DB
        if self._db_session is not None and self._model is not None:
            try:
                from sqlalchemy import select  # type: ignore[import-not-found]

                stmt = select(self._model).where(self._model.user_id == user_id)
                rows = self._db_session.execute(stmt).scalars().all()
                for row in rows:
                    row.revoked = True
                self._db_session.commit()
            except Exception:
                logger.exception("Failed to revoke user sessions in database")
                try:
                    self._db_session.rollback()
                except Exception:
                    pass

        return len(session_ids)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_active_sessions(self, user_id: str | None = None) -> list[dict[str, Any]]:
        """Get all active (non-expired, non-revoked) sessions.

        Optionally filter by *user_id*.  Returns a list of dicts.
        """
        results: list[dict[str, Any]] = []
        for sid, session in self._sessions.items():
            # Skip revoked
            if session.get("revoked") or not session.get("active", True):
                continue
            # Skip expired
            if self._is_expired(session):
                self._remove_from_memory(sid)
                continue
            # Filter by user
            if user_id is not None and session.get("user_id") != user_id:
                continue

            results.append(dict(session))

        results.sort(key=lambda s: s.get("created_at", ""), reverse=True)
        return results

    def cleanup_expired(self) -> int:
        """Remove all expired sessions from the in-memory store.

        Returns the count of removed sessions.
        """
        expired_ids = [
            sid
            for sid, session in self._sessions.items()
            if self._is_expired(session) or session.get("revoked", False)
        ]

        for sid in expired_ids:
            self._remove_from_memory(sid)

        return len(expired_ids)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_expired(self, session: dict[str, Any]) -> bool:
        """Return True if the session has expired."""
        expires_at_str = session.get("expires_at", "")
        if not expires_at_str:
            return True

        now = datetime.datetime.now(datetime.timezone.utc)
        try:
            expires_at = datetime.datetime.fromisoformat(expires_at_str)
            # Make timezone-aware if naive
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=datetime.timezone.utc)
            return now >= expires_at
        except (ValueError, TypeError):
            return True

    def _remove_from_memory(self, session_id: str) -> None:
        """Safely remove a session from the in-memory store."""
        self._sessions.pop(session_id, None)
