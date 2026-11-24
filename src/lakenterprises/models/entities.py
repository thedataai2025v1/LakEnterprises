"""SQLAlchemy ORM entity classes for the LakEnterprises platform."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (JSON, Boolean, Column, DateTime, Float, ForeignKey,
                        Integer, String, Table, Text, func)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin

# ── Association tables ────────────────────────────────────────────────

role_user = Table(
    "role_user",
    Base.metadata,
    Column("user_id", String(36), ForeignKey("user.id"), primary_key=True),
    Column("role_id", String(36), ForeignKey("role.id"), primary_key=True),
)

role_permission = Table(
    "role_permission",
    Base.metadata,
    Column("role_id", String(36), ForeignKey("role.id"), primary_key=True),
    Column("permission_id", String(36), ForeignKey("permission.id"), primary_key=True),
)


# ── Phase 2 entities (unchanged) ──────────────────────────────────────


class Document(Base, UUIDMixin):
    """Chunked document ingested into the platform."""

    __tablename__ = "document"

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    chunks: Mapped[List[DocumentChunk]] = relationship(
        "DocumentChunk", back_populates="document", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Document id={self.id!r} name={self.name!r}>"


class DocumentChunk(Base):
    """A text chunk extracted from a document."""

    __tablename__ = "document_chunk"

    id: Mapped[int] = mapped_column(primary_key=True)
    chunk_id: Mapped[str] = mapped_column(
        String(64), unique=True, default=lambda: str(uuid.uuid4()), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("document.id"), nullable=False
    )
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    embedding: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)
    word_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    document: Mapped[Document] = relationship("Document", back_populates="chunks")

    def __repr__(self) -> str:
        return f"<DocumentChunk id={self.id} chunk_id={self.chunk_id!r}>"


class ResearchSession(Base, UUIDMixin, TimestampMixin):
    """A multi-step research conversation session."""

    __tablename__ = "research_session"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)

    user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("user.id"), nullable=True
    )
    user: Mapped[Optional[User]] = relationship(
        "User", back_populates="research_sessions"
    )

    sub_questions: Mapped[List[ResearchSubQuestion]] = relationship(
        "ResearchSubQuestion", back_populates="session", cascade="all, delete-orphan"
    )
    events: Mapped[List[WorkflowEvent]] = relationship(
        "WorkflowEvent", back_populates="session", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<ResearchSession id={self.id!r} title={self.title!r} status={self.status!r}>"


class ResearchSubQuestion(Base):
    """A sub-question spawned from a research session."""

    __tablename__ = "research_sub_question"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("research_session.id"), nullable=False
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    session: Mapped[ResearchSession] = relationship(
        "ResearchSession", back_populates="sub_questions"
    )

    def __repr__(self) -> str:
        return f"<ResearchSubQuestion id={self.id} question={self.question!r} status={self.status!r}>"


class WorkflowEvent(Base):
    """An event in a research session workflow."""

    __tablename__ = "workflow_event"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("research_session.id"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    session: Mapped[ResearchSession] = relationship(
        "ResearchSession", back_populates="events"
    )

    def __repr__(self) -> str:
        return f"<WorkflowEvent id={self.id} event_type={self.event_type!r}>"


class AuditLog(Base):
    """Audit log entry."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    entry_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    entity_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    entity_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    severity: Mapped[str] = mapped_column(String(20), default="INFO", nullable=False)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<AuditLog id={self.id} action={self.action!r}>"


# ── Phase 3 entities ──────────────────────────────────────────────────


class User(Base, UUIDMixin, TimestampMixin):
    """Authenticated platform user."""

    __tablename__ = "user"

    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    roles: Mapped[List[Role]] = relationship(
        "Role", secondary=role_user, back_populates="users"
    )
    auth_tokens: Mapped[List[AuthToken]] = relationship(
        "AuthToken", back_populates="user", cascade="all, delete-orphan"
    )
    research_sessions: Mapped[List[ResearchSession]] = relationship(
        "ResearchSession", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id!r} username={self.username!r} email={self.email!r}>"


class Role(Base, UUIDMixin, TimestampMixin):
    """Named role with an associated set of permissions."""

    __tablename__ = "role"

    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    permissions: Mapped[List[Permission]] = relationship(
        "Permission", secondary=role_permission, back_populates="roles"
    )
    users: Mapped[List[User]] = relationship(
        "User", secondary=role_user, back_populates="roles"
    )

    def __repr__(self) -> str:
        return f"<Role id={self.id!r} name={self.name!r}>"


class Permission(Base, UUIDMixin):
    """A single permission (e.g. CREATE_USER)."""

    __tablename__ = "permission"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    module: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    roles: Mapped[List[Role]] = relationship(
        "Role", secondary=role_permission, back_populates="permissions"
    )

    def __repr__(self) -> str:
        return f"<Permission id={self.id!r} name={self.name!r}>"


class AuthToken(Base, TimestampMixin):
    """Persisted access/refresh token pair for a user."""

    __tablename__ = "auth_token"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("user.id"), nullable=False
    )
    token: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    refresh_token_hash: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    token_type: Mapped[str] = mapped_column(
        String(20), default="access", nullable=False
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    @property
    def revoked(self) -> bool:
        return self.is_revoked

    @revoked.setter
    def revoked(self, val: bool) -> None:
        self.is_revoked = val

    user: Mapped[User] = relationship("User", back_populates="auth_tokens")

    def __repr__(self) -> str:
        return f"<AuthToken id={self.id!r} user_id={self.user_id!r} is_revoked={self.is_revoked}>"


# ── Phase 5 entities (Enterprise Process & Approval) ───────────────────────


class ProcessTemplate(Base, UUIDMixin, TimestampMixin):
    """Reusable blueprint defining an enterprise business process."""

    __tablename__ = "process_template"

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    definition: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    instances: Mapped[List[ProcessInstance]] = relationship(
        "ProcessInstance", back_populates="template", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<ProcessTemplate id={self.id!r} name={self.name!r} v={self.version}>"


class ProcessInstance(Base, UUIDMixin, TimestampMixin):
    """Execution instance of a process template with runtime state and context."""

    __tablename__ = "process_instance"

    template_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("process_template.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    context: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, nullable=True)
    created_by_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("user.id"), nullable=True
    )

    template: Mapped[ProcessTemplate] = relationship(
        "ProcessTemplate", back_populates="instances"
    )
    tasks: Mapped[List[ProcessTask]] = relationship(
        "ProcessTask",
        back_populates="instance",
        cascade="all, delete-orphan",
        order_by="ProcessTask.position",
    )

    def __repr__(self) -> str:
        return f"<ProcessInstance id={self.id!r} title={self.title!r} status={self.status!r}>"


class ProcessTask(Base, UUIDMixin, TimestampMixin):
    """Granular unit of work inside a process instance."""

    __tablename__ = "process_task"

    instance_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("process_instance.id"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assignee_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    assignee_role: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    instance: Mapped[ProcessInstance] = relationship(
        "ProcessInstance", back_populates="tasks"
    )

    def __repr__(self) -> str:
        return f"<ProcessTask id={self.id!r} name={self.name!r} pos={self.position} status={self.status!r}>"


class ApprovalRequest(Base, UUIDMixin, TimestampMixin):
    """Governance gate requiring human sign-off for critical actions."""

    __tablename__ = "approval_request"

    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    requested_by_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    reviewed_by_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<ApprovalRequest id={self.id!r} action={self.action!r} status={self.status!r}>"
