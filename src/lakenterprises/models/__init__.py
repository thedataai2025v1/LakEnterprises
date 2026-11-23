"""ORM models package – imports all entities to register them with SQLAlchemy."""

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from .enums import (
    ApprovalStatus,
    AuditAction,
    DocumentStatus,
    DocumentType,
    EventType,
    ProcessStatus,
    QueryComplexity,
    RetrievalStrategy,
    SessionStatus,
    TaskStatus,
    UserRole,
    UserStatus,
)
from .entities import (
    ApprovalRequest,
    AuditLog,
    Document,
    DocumentChunk,
    ProcessInstance,
    ProcessTask,
    ProcessTemplate,
    ResearchSession,
    ResearchSubQuestion,
    User,
    WorkflowEvent,
)

__all__ = [
    # base
    "Base",
    "TimestampMixin",
    "UUIDPrimaryKeyMixin",
    # enums
    "ApprovalStatus",
    "AuditAction",
    "DocumentStatus",
    "DocumentType",
    "EventType",
    "ProcessStatus",
    "QueryComplexity",
    "RetrievalStrategy",
    "SessionStatus",
    "TaskStatus",
    "UserRole",
    "UserStatus",
    # entities
    "ApprovalRequest",
    "AuditLog",
    "Document",
    "DocumentChunk",
    "ProcessInstance",
    "ProcessTask",
    "ProcessTemplate",
    "ResearchSession",
    "ResearchSubQuestion",
    "User",
    "WorkflowEvent",
]
