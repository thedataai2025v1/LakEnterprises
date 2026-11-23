"""SQLAlchemy declarative base and shared column helpers.

Keeping the Base here (rather than in a per-entity file) prevents
circular imports between entity modules.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, String, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    """Return the current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    """Return a new UUIDv4 string."""
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    """Project-wide SQLAlchemy declarative base.

    Every model that inherits from this automatically gets:
    - ``__tablename__`` derived from the class name (snake_case expected from
      sub-classes that set it explicitly).
    - A ``to_dict()`` helper for simple serialisation.
    """

    # Allow extra attributes on instances (useful for in-memory test helpers)
    __allow_unmapped__ = False

    def to_dict(self) -> dict[str, Any]:
        """Return a plain-dict snapshot of all mapped columns."""
        return {
            col.key: getattr(self, col.key)
            for col in self.__mapper__.column_attrs  # type: ignore[attr-defined]
        }

    def __repr__(self) -> str:
        pk_cols = [c.key for c in self.__mapper__.primary_key]  # type: ignore[attr-defined]
        pk_parts = ", ".join(f"{k}={getattr(self, k)!r}" for k in pk_cols)
        return f"<{type(self).__name__} {pk_parts}>"


# ---------------------------------------------------------------------------
# Mixin – id + timestamps (re-used by most tables)
# ---------------------------------------------------------------------------


class TimestampMixin:
    """Adds ``created_at`` / ``updated_at`` columns with auto-fill."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        nullable=False,
        doc="Row creation timestamp (UTC).",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        nullable=False,
        doc="Last-update timestamp (UTC).",
    )


class UUIDPrimaryKeyMixin:
    """Adds a UUID primary-key column named ``id``."""

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_new_uuid,
        doc="UUID primary key (string form).",
    )
