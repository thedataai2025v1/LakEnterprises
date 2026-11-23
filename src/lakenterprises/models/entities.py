"""SQLAlchemy ORM entity definitions for the LakEnterprises platform.

Tables
------
users                  – platform users with RBAC roles
documents              – uploaded knowledge-base documents
document_chunks        – chunked segments of documents (for vector retrieval)
research_sessions      – one row per analyst research question
research_sub_questions – sub-questions decomposed from one session
workflow_events        – fine-grained event log for a session
audit_log              – immutable record of every mutating action
process_templates      – reusable enterprise-process templates (Phase 5 schema)
process_instances      – live instances of a process template
process_tasks          – individual tasks inside an instance
approval_requests      – approval records for gated actions
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin, _new_uuid, _utcnow
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


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Platform user, identified by email, assigned one RBAC role."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(32), nullable=False, default=UserRole.viewer.value
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=UserStatus.active.value
    )
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Back-refs
    research_sessions: Mapped[list["ResearchSession"]] = relationship(
        "ResearchSession", back_populates="user", cascade="all, delete-orphan"
    )
    audit_entries: Mapped[list["AuditLog"]] = relationship(
        "AuditLog", back_populates="user", cascade="all, delete-orphan"
    )
    documents: Mapped[list["Document"]] = relationship(
        "Document", back_populates="uploader", cascade="all, delete-orphan"
    )
    approval_decisions: Mapped[list["ApprovalRequest"]] = relationship(
        "ApprovalRequest",
        foreign_keys="ApprovalRequest.decided_by_id",
        back_populates="decided_by",
    )

    @property
    def role_enum(self) -> UserRole:
        return UserRole(self.role)

    @property
    def status_enum(self) -> UserStatus:
        return UserStatus(self.status)


# ---------------------------------------------------------------------------
# Document
# ---------------------------------------------------------------------------


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Uploaded knowledge-base document (before or after chunking)."""

    __tablename__ = "documents"

    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    doc_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default=DocumentType.other.value
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=DocumentStatus.pending.value
    )
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    uploader_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    uploader: Mapped["User"] = relationship("User", back_populates="documents")
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk", back_populates="document", cascade="all, delete-orphan"
    )
    approval_requests: Mapped[list["ApprovalRequest"]] = relationship(
        "ApprovalRequest",
        foreign_keys="ApprovalRequest.target_id",
        primaryjoin="and_(ApprovalRequest.target_id == Document.id, "
                    "ApprovalRequest.target_type == 'document')",
        cascade="all, delete-orphan",
        overlaps="approval_requests",
    )

    @property
    def metadata(self) -> dict[str, Any]:
        return json.loads(self.metadata_json or "{}")

    @metadata.setter
    def metadata(self, value: dict[str, Any]) -> None:
        self.metadata_json = json.dumps(value)

    @property
    def status_enum(self) -> DocumentStatus:
        return DocumentStatus(self.status)


# ---------------------------------------------------------------------------
# DocumentChunk
# ---------------------------------------------------------------------------


class DocumentChunk(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One chunked segment of a document, ready for vector embedding."""

    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_chunk_per_doc"),
    )

    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    # vector_id stores the ID assigned by the external vector store (Qdrant, Chroma…)
    vector_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    document: Mapped["Document"] = relationship("Document", back_populates="chunks")

    @property
    def metadata(self) -> dict[str, Any]:
        return json.loads(self.metadata_json or "{}")

    @metadata.setter
    def metadata(self, value: dict[str, Any]) -> None:
        self.metadata_json = json.dumps(value)


# ---------------------------------------------------------------------------
# ResearchSession
# ---------------------------------------------------------------------------


class ResearchSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One research session created by an analyst's question."""

    __tablename__ = "research_sessions"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    complexity: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=SessionStatus.running.value
    )
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    citations_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Timing
    started_at: Mapped[datetime | None] = mapped_column(
        "started_at", String(64), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        "completed_at", String(64), nullable=True
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="research_sessions")
    sub_questions: Mapped[list["ResearchSubQuestion"]] = relationship(
        "ResearchSubQuestion",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ResearchSubQuestion.position",
    )
    events: Mapped[list["WorkflowEvent"]] = relationship(
        "WorkflowEvent", back_populates="session", cascade="all, delete-orphan"
    )

    @property
    def citations(self) -> list[str]:
        return json.loads(self.citations_json or "[]")

    @citations.setter
    def citations(self, value: list[str]) -> None:
        self.citations_json = json.dumps(value)

    @property
    def metadata(self) -> dict[str, Any]:
        return json.loads(self.metadata_json or "{}")

    @metadata.setter
    def metadata(self, value: dict[str, Any]) -> None:
        self.metadata_json = json.dumps(value)

    @property
    def status_enum(self) -> SessionStatus:
        return SessionStatus(self.status)

    @property
    def complexity_enum(self) -> QueryComplexity | None:
        return QueryComplexity(self.complexity) if self.complexity else None


# ---------------------------------------------------------------------------
# ResearchSubQuestion
# ---------------------------------------------------------------------------


class ResearchSubQuestion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One sub-question produced by the decompose node of a session."""

    __tablename__ = "research_sub_questions"

    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("research_sessions.id"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    strategy: Mapped[str] = mapped_column(
        String(32), nullable=False, default=RetrievalStrategy.vector.value
    )
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verification_ratio: Mapped[float | None] = mapped_column(
        "verification_ratio", String(16), nullable=True
    )

    session: Mapped["ResearchSession"] = relationship(
        "ResearchSession", back_populates="sub_questions"
    )

    @property
    def evidence(self) -> list[dict[str, Any]]:
        return json.loads(self.evidence_json or "[]")

    @evidence.setter
    def evidence(self, value: list[dict[str, Any]]) -> None:
        self.evidence_json = json.dumps(value)

    @property
    def strategy_enum(self) -> RetrievalStrategy:
        return RetrievalStrategy(self.strategy)


# ---------------------------------------------------------------------------
# WorkflowEvent
# ---------------------------------------------------------------------------


class WorkflowEvent(UUIDPrimaryKeyMixin, Base):
    """Fine-grained immutable event emitted during a research run.

    Intentionally has no ``updated_at``; events are write-once.
    """

    __tablename__ = "workflow_events"

    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("research_sessions.id"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(
        String(64), nullable=False, default=EventType.node_start.value
    )
    node_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[str] = mapped_column(
        String(64), default=lambda: _utcnow().isoformat(), nullable=False
    )

    session: Mapped["ResearchSession"] = relationship(
        "ResearchSession", back_populates="events"
    )

    @property
    def payload(self) -> dict[str, Any]:
        return json.loads(self.payload_json or "{}")

    @payload.setter
    def payload(self, value: dict[str, Any]) -> None:
        self.payload_json = json.dumps(value)


# ---------------------------------------------------------------------------
# AuditLog
# ---------------------------------------------------------------------------


class AuditLog(UUIDPrimaryKeyMixin, Base):
    """Immutable audit trail – one row per mutating action.

    Intentionally has no ``updated_at`` column.
    """

    __tablename__ = "audit_log"

    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    detail_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[str] = mapped_column(
        String(64), default=lambda: _utcnow().isoformat(), nullable=False
    )

    user: Mapped["User | None"] = relationship("User", back_populates="audit_entries")

    @property
    def detail(self) -> dict[str, Any]:
        return json.loads(self.detail_json or "{}")

    @detail.setter
    def detail(self, value: dict[str, Any]) -> None:
        self.detail_json = json.dumps(value)


# ---------------------------------------------------------------------------
# ProcessTemplate  (Phase 5 schema – seeded now so migrations are stable)
# ---------------------------------------------------------------------------


class ProcessTemplate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Reusable blueprint describing an enterprise workflow."""

    __tablename__ = "process_templates"

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    definition_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )

    instances: Mapped[list["ProcessInstance"]] = relationship(
        "ProcessInstance", back_populates="template", cascade="all, delete-orphan"
    )

    @property
    def definition(self) -> dict[str, Any]:
        return json.loads(self.definition_json or "{}")

    @definition.setter
    def definition(self, value: dict[str, Any]) -> None:
        self.definition_json = json.dumps(value)


# ---------------------------------------------------------------------------
# ProcessInstance
# ---------------------------------------------------------------------------


class ProcessInstance(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Live execution of a ProcessTemplate for a specific case."""

    __tablename__ = "process_instances"

    template_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("process_templates.id"), nullable=False, index=True
    )
    initiated_by_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ProcessStatus.active.value
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    context_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    result_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    research_session_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("research_sessions.id"), nullable=True
    )

    template: Mapped["ProcessTemplate"] = relationship(
        "ProcessTemplate", back_populates="instances"
    )
    tasks: Mapped[list["ProcessTask"]] = relationship(
        "ProcessTask",
        back_populates="instance",
        cascade="all, delete-orphan",
        order_by="ProcessTask.position",
    )
    approval_requests: Mapped[list["ApprovalRequest"]] = relationship(
        "ApprovalRequest",
        foreign_keys="ApprovalRequest.target_id",
        primaryjoin="and_(ApprovalRequest.target_id == ProcessInstance.id, "
                    "ApprovalRequest.target_type == 'process_instance')",
        cascade="all, delete-orphan",
        overlaps="approval_requests",
    )

    @property
    def context(self) -> dict[str, Any]:
        return json.loads(self.context_json or "{}")

    @context.setter
    def context(self, value: dict[str, Any]) -> None:
        self.context_json = json.dumps(value)

    @property
    def result(self) -> dict[str, Any]:
        return json.loads(self.result_json or "{}")

    @result.setter
    def result(self, value: dict[str, Any]) -> None:
        self.result_json = json.dumps(value)


# ---------------------------------------------------------------------------
# ProcessTask
# ---------------------------------------------------------------------------


class ProcessTask(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One step within a ProcessInstance."""

    __tablename__ = "process_tasks"

    instance_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("process_instances.id"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=TaskStatus.pending.value
    )
    assigned_to_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    result_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    instance: Mapped["ProcessInstance"] = relationship(
        "ProcessInstance", back_populates="tasks"
    )

    @property
    def result(self) -> dict[str, Any]:
        return json.loads(self.result_json or "{}")

    @result.setter
    def result(self, value: dict[str, Any]) -> None:
        self.result_json = json.dumps(value)


# ---------------------------------------------------------------------------
# ApprovalRequest
# ---------------------------------------------------------------------------


class ApprovalRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Gate on a potentially destructive or high-impact action."""

    __tablename__ = "approval_requests"

    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    requested_by_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    decided_by_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ApprovalStatus.pending.value
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    decided_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[decided_by_id],
        back_populates="approval_decisions",
    )

    @property
    def status_enum(self) -> ApprovalStatus:
        return ApprovalStatus(self.status)
