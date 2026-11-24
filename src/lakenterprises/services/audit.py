"""Audit logging service.

Records and queries audit log entries.  Works in-memory by default; when
``db_session`` is provided it also persists to / queries from the
database via the ``AuditLog`` ORM model (lazy-imported so the service
is usable even without SQLAlchemy).
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


def _get_audit_log_model() -> type | None:
    """Lazy-load the AuditLog ORM model, if available."""
    try:
        from lakenterprises.models.entities import \
            AuditLog  # type: ignore[import-not-found, no-redef]

        return AuditLog
    except Exception:  # noqa: S110
        return None


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class AuditService:
    """Service for recording and querying audit log entries.

    Parameters
    ----------
    db_session:
        A SQLAlchemy session (or None for in-memory-only mode).
    """

    def __init__(self, db_session: Any = None) -> None:
        self._db_session = db_session
        self._logs: list[dict[str, Any]] = []
        self._model = _get_audit_log_model()

    # ------------------------------------------------------------------
    # Writing
    # ------------------------------------------------------------------

    def log(
        self,
        action: str,
        user_id: str | None,
        details: dict | None = None,
        severity: str = "INFO",
        ip_address: str | None = None,
    ) -> dict[str, Any]:
        """Create an audit log entry.

        Returns a dict with keys: ``entry_id``, ``action``, ``user_id``,
        ``timestamp``, ``severity``, ``details``, ``ip_address``.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        entry_id = str(uuid.uuid4())

        entry: dict[str, Any] = {
            "entry_id": entry_id,
            "action": action,
            "user_id": user_id,
            "timestamp": now.isoformat(),
            "severity": severity.upper(),
            "details": details if details is not None else {},
            "ip_address": ip_address,
        }

        # Persist in-memory
        self._logs.append(entry)

        # Persist to DB if available
        if self._db_session is not None and self._model is not None:
            try:
                db_entry = self._model(
                    entry_id=entry_id,
                    action=action,
                    user_id=user_id,
                    timestamp=now,
                    severity=entry["severity"],
                    details=details,
                    ip_address=ip_address,
                )
                self._db_session.add(db_entry)
                self._db_session.commit()
            except Exception:
                logger.exception("Failed to persist audit entry to database")
                try:
                    self._db_session.rollback()
                except Exception:
                    pass

        return entry

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def get_logs(
        self,
        user_id: str | None = None,
        action: str | None = None,
        start_date: datetime.datetime | None = None,
        end_date: datetime.datetime | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query audit logs with optional filters.

        Returns a list of dicts, most recent first.
        """
        if self._db_session is not None and self._model is not None:
            return self._get_logs_from_db(user_id, action, start_date, end_date, limit)

        return self._get_logs_from_memory(user_id, action, start_date, end_date, limit)

    def get_user_activity(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent activity for a specific user.

        Returns a list of dicts, most recent first.
        """
        if not user_id:
            return []
        return self.get_logs(user_id=user_id, limit=limit)

    def get_security_events(
        self, severity: str = "WARNING", limit: int = 50
    ) -> list[dict[str, Any]]:
        """Get security-relevant events (WARNING, ERROR, CRITICAL).

        If *severity* is given, only entries matching that level (and above)
        are returned.  The default ``"WARNING"`` includes WARNING, ERROR and
        CRITICAL.

        Returns a list of dicts, most recent first.
        """
        severity = severity.upper()
        severity_levels = ["INFO", "WARNING", "ERROR", "CRITICAL"]

        try:
            min_index = severity_levels.index(severity)
        except ValueError:
            min_index = 0

        allowed = severity_levels[min_index:]

        if self._db_session is not None and self._model is not None:
            return self._get_security_events_from_db(allowed, limit)

        return self._get_security_events_from_memory(allowed, limit)

    # ------------------------------------------------------------------
    # Internal helpers — in-memory
    # ------------------------------------------------------------------

    def _get_logs_from_memory(
        self,
        user_id: str | None,
        action: str | None,
        start_date: datetime.datetime | None,
        end_date: datetime.datetime | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []

        for entry in self._logs:
            if user_id is not None and entry.get("user_id") != user_id:
                continue
            if action is not None and entry.get("action") != action:
                continue

            entry_ts = entry.get("timestamp", "")
            if start_date is not None:
                try:
                    ts = datetime.datetime.fromisoformat(entry_ts)
                    if ts < start_date:
                        continue
                except (ValueError, TypeError):
                    continue
            if end_date is not None:
                try:
                    ts = datetime.datetime.fromisoformat(entry_ts)
                    if ts > end_date:
                        continue
                except (ValueError, TypeError):
                    continue

            results.append(dict(entry))

        results.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
        return results[:limit]

    def _get_security_events_from_memory(
        self, allowed: list[str], limit: int
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []

        for entry in self._logs:
            if entry.get("severity", "") not in allowed:
                continue
            results.append(dict(entry))

        results.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
        return results[:limit]

    # ------------------------------------------------------------------
    # Internal helpers — database
    # ------------------------------------------------------------------

    def _get_logs_from_db(
        self,
        user_id: str | None,
        action: str | None,
        start_date: datetime.datetime | None,
        end_date: datetime.datetime | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        try:
            from sqlalchemy import select  # type: ignore[import-not-found]
        except ImportError:
            # Fallback to in-memory if SQLAlchemy isn't available
            return self._get_logs_from_memory(
                user_id, action, start_date, end_date, limit
            )

        stmt = select(self._model)

        if user_id is not None:
            stmt = stmt.where(self._model.user_id == user_id)
        if action is not None:
            stmt = stmt.where(self._model.action == action)
        if start_date is not None:
            stmt = stmt.where(self._model.timestamp >= start_date)
        if end_date is not None:
            stmt = stmt.where(self._model.timestamp <= end_date)

        stmt = stmt.order_by(self._model.timestamp.desc()).limit(limit)

        try:
            rows = self._db_session.execute(stmt).scalars().all()
        except Exception:
            logger.exception("Failed to query audit logs from database")
            return self._get_logs_from_memory(
                user_id, action, start_date, end_date, limit
            )

        return [self._audit_row_to_dict(row) for row in rows]

    def _get_security_events_from_db(
        self, allowed: list[str], limit: int
    ) -> list[dict[str, Any]]:
        try:
            from sqlalchemy import select  # type: ignore[import-not-found]
        except ImportError:
            return self._get_security_events_from_memory(allowed, limit)

        stmt = select(self._model)
        stmt = stmt.where(self._model.severity.in_(allowed))
        stmt = stmt.order_by(self._model.timestamp.desc()).limit(limit)

        try:
            rows = self._db_session.execute(stmt).scalars().all()
        except Exception:
            logger.exception("Failed to query security events from database")
            return self._get_security_events_from_memory(allowed, limit)

        return [self._audit_row_to_dict(row) for row in rows]

    def _audit_row_to_dict(self, row: Any) -> dict[str, Any]:
        """Convert an ORM row to a plain dict."""
        result: dict[str, Any] = {}
        for col in row.__table__.columns:  # type: ignore[union-attr]
            attr = getattr(row, col.name, None)
            if isinstance(attr, datetime.datetime):
                result[col.name] = attr.isoformat()
            else:
                result[col.name] = attr
        return result
