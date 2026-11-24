"""Enumeration types used by the identity and data models."""

from enum import Enum


class RoleType(str, Enum):
    """Standard user roles."""

    ADMIN = "ADMIN"
    EDITOR = "EDITOR"
    VIEWER = "VIEWER"


class PermissionType(str, Enum):
    """Granular permission identifiers."""

    CREATE_USER = "CREATE_USER"
    READ_USER = "READ_USER"
    UPDATE_USER = "UPDATE_USER"
    DELETE_USER = "DELETE_USER"
    CREATE_DOCUMENT = "CREATE_DOCUMENT"
    READ_DOCUMENT = "READ_DOCUMENT"
    UPDATE_DOCUMENT = "UPDATE_DOCUMENT"
    DELETE_DOCUMENT = "DELETE_DOCUMENT"
    CREATE_SESSION = "CREATE_SESSION"
    READ_SESSION = "READ_SESSION"
    UPDATE_SESSION = "UPDATE_SESSION"
    DELETE_SESSION = "DELETE_SESSION"
    MANAGE_ROLES = "MANAGE_ROLES"
    VIEW_AUDIT_LOG = "VIEW_AUDIT_LOG"


class AuditAction(str, Enum):
    """Actions recorded in the audit log."""

    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    GRANT_PERMISSION = "GRANT_PERMISSION"
    REVOKE_PERMISSION = "REVOKE_PERMISSION"
    ASSIGN_ROLE = "ASSIGN_ROLE"
    TOKEN_REFRESH = "TOKEN_REFRESH"
    SESSION_EXPIRED = "SESSION_EXPIRED"


class AuditSeverity(str, Enum):
    """Severity level for audit entries."""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ProcessStatus(str, Enum):
    """Process instance lifecycle states."""

    PENDING = "pending"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskStatus(str, Enum):
    """Process task lifecycle states."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ApprovalStatus(str, Enum):
    """Approval request review status."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
