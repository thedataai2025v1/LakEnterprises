"""Shared enumerations for the LakEnterprises data model.

All enums are defined as Python native `enum.Enum` subclasses so they
work both with SQLAlchemy (stored as VARCHAR) and in pure-Python code
(no DB connection required).
"""

from __future__ import annotations

import enum


# ---------------------------------------------------------------------------
# User / Identity
# ---------------------------------------------------------------------------


class UserRole(str, enum.Enum):
    """Roles that drive RBAC decisions throughout the platform."""

    viewer = "viewer"
    analyst = "analyst"
    admin = "admin"


class UserStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    suspended = "suspended"


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


class DocumentStatus(str, enum.Enum):
    pending = "pending"       # just uploaded, not yet ingested
    processing = "processing"  # chunking / embedding in progress
    indexed = "indexed"        # fully searchable
    failed = "failed"          # ingestion error
    deleted = "deleted"        # soft-deleted, approval pending or complete


class DocumentType(str, enum.Enum):
    markdown = "markdown"
    text = "text"
    pdf = "pdf"
    csv = "csv"
    json = "json"
    other = "other"


# ---------------------------------------------------------------------------
# Research sessions
# ---------------------------------------------------------------------------


class SessionStatus(str, enum.Enum):
    running = "running"
    completed = "completed"
    failed = "failed"


class RetrievalStrategy(str, enum.Enum):
    vector = "vector"
    sql = "sql"
    graph = "graph"
    hybrid = "hybrid"


class QueryComplexity(str, enum.Enum):
    simple = "simple"
    moderate = "moderate"
    complex = "complex"


# ---------------------------------------------------------------------------
# Enterprise processes (Phase 5 tables are seeded here too)
# ---------------------------------------------------------------------------


class ProcessStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    completed = "completed"
    cancelled = "cancelled"
    escalated = "escalated"


class TaskStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"


class ApprovalStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    escalated = "escalated"


# ---------------------------------------------------------------------------
# Audit / events
# ---------------------------------------------------------------------------


class AuditAction(str, enum.Enum):
    create = "create"
    read = "read"
    update = "update"
    delete = "delete"
    approve = "approve"
    reject = "reject"
    escalate = "escalate"
    upload = "upload"
    ingest = "ingest"
    login = "login"
    logout = "logout"


class EventType(str, enum.Enum):
    """Workflow-event types emitted during a research run."""

    node_start = "node_start"
    node_end = "node_end"
    tool_call = "tool_call"
    retrieval = "retrieval"
    llm_call = "llm_call"
    error = "error"
    escalation = "escalation"
    approval_request = "approval_request"
    approval_decision = "approval_decision"
