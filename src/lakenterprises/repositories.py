"""Repository layer for the LakEnterprises platform.

Each repository class wraps one SQLAlchemy table and exposes typed CRUD
operations.  Repositories never import from FastAPI – they only know
about SQLAlchemy sessions and domain models.

Import direction (enforced at module level):
    API → Services → Repositories → Models/DB

Usage
-----
    from lakenterprises.repositories import UserRepository

    with db_session() as db:
        repo = UserRepository(db)
        user = repo.get_by_email("alice@example.com")
"""

from __future__ import annotations

from typing import Any, Generic, List, Optional, Sequence, Type, TypeVar

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .models import (
    ApprovalRequest,
    ApprovalStatus,
    AuditLog,
    Document,
    DocumentChunk,
    DocumentStatus,
    ProcessInstance,
    ProcessTask,
    ProcessTemplate,
    ResearchSession,
    ResearchSubQuestion,
    SessionStatus,
    User,
    UserRole,
    WorkflowEvent,
)
from .models.base import Base

ModelT = TypeVar("ModelT", bound=Base)


# ---------------------------------------------------------------------------
# Base repository
# ---------------------------------------------------------------------------


class BaseRepository(Generic[ModelT]):
    """Generic CRUD repository.

    Sub-classes set ``model`` to the ORM class they manage.
    """

    model: Type[ModelT]

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Create ──────────────────────────────────────────────────────────────

    def create(self, **kwargs: Any) -> ModelT:
        """Instantiate *model*, add to session, flush (get PK), return."""
        instance = self.model(**kwargs)
        self.db.add(instance)
        self.db.flush()
        return instance

    # ── Read ────────────────────────────────────────────────────────────────

    def get(self, id: str) -> Optional[ModelT]:
        """Return the row with the given primary key, or ``None``."""
        return self.db.get(self.model, id)

    def get_or_raise(self, id: str) -> ModelT:
        """Return the row or raise ``KeyError`` if not found."""
        obj = self.get(id)
        if obj is None:
            raise KeyError(f"{self.model.__name__} with id={id!r} not found")
        return obj

    def list_all(self, limit: int = 100, offset: int = 0) -> List[ModelT]:
        """Return a paginated slice of all rows."""
        stmt = select(self.model).limit(limit).offset(offset)
        return list(self.db.scalars(stmt).all())

    def count(self) -> int:
        """Return the total number of rows in the table."""
        from sqlalchemy import func
        result = self.db.execute(select(func.count()).select_from(self.model))
        return result.scalar_one()

    # ── Update ──────────────────────────────────────────────────────────────

    def update(self, id: str, **kwargs: Any) -> Optional[ModelT]:
        """Update columns by name; return the updated row or ``None``."""
        obj = self.get(id)
        if obj is None:
            return None
        for key, value in kwargs.items():
            setattr(obj, key, value)
        self.db.flush()
        return obj

    # ── Delete ──────────────────────────────────────────────────────────────

    def delete(self, id: str) -> bool:
        """Hard-delete the row; returns ``True`` if it existed."""
        obj = self.get(id)
        if obj is None:
            return False
        self.db.delete(obj)
        self.db.flush()
        return True


# ---------------------------------------------------------------------------
# UserRepository
# ---------------------------------------------------------------------------


class UserRepository(BaseRepository[User]):
    model = User

    def get_by_email(self, email: str) -> Optional[User]:
        stmt = select(User).where(User.email == email)
        return self.db.scalars(stmt).first()

    def get_by_role(self, role: UserRole | str) -> List[User]:
        role_value = role.value if isinstance(role, UserRole) else role
        stmt = select(User).where(User.role == role_value)
        return list(self.db.scalars(stmt).all())

    def list_active(self, limit: int = 100, offset: int = 0) -> List[User]:
        stmt = select(User).where(User.status == "active").limit(limit).offset(offset)
        return list(self.db.scalars(stmt).all())

    def email_exists(self, email: str) -> bool:
        return self.get_by_email(email) is not None


# ---------------------------------------------------------------------------
# DocumentRepository
# ---------------------------------------------------------------------------


class DocumentRepository(BaseRepository[Document]):
    model = Document

    def get_by_uploader(self, user_id: str) -> List[Document]:
        stmt = select(Document).where(Document.uploader_id == user_id)
        return list(self.db.scalars(stmt).all())

    def list_by_status(
        self, status: DocumentStatus | str, limit: int = 100, offset: int = 0
    ) -> List[Document]:
        status_value = status.value if isinstance(status, DocumentStatus) else status
        stmt = (
            select(Document)
            .where(Document.status == status_value)
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(stmt).all())

    def soft_delete(self, id: str) -> Optional[Document]:
        """Mark as deleted without removing the row."""
        return self.update(id, status=DocumentStatus.deleted.value)

    def set_status(self, id: str, status: DocumentStatus | str) -> Optional[Document]:
        status_value = status.value if isinstance(status, DocumentStatus) else status
        return self.update(id, status=status_value)

    def increment_chunk_count(self, id: str, count: int = 1) -> Optional[Document]:
        obj = self.get(id)
        if obj is None:
            return None
        obj.chunk_count += count
        self.db.flush()
        return obj


# ---------------------------------------------------------------------------
# DocumentChunkRepository
# ---------------------------------------------------------------------------


class DocumentChunkRepository(BaseRepository[DocumentChunk]):
    model = DocumentChunk

    def get_by_document(self, document_id: str) -> List[DocumentChunk]:
        stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
        )
        return list(self.db.scalars(stmt).all())

    def delete_by_document(self, document_id: str) -> int:
        """Delete all chunks for a document; returns the count deleted."""
        chunks = self.get_by_document(document_id)
        for chunk in chunks:
            self.db.delete(chunk)
        self.db.flush()
        return len(chunks)

    def get_by_vector_id(self, vector_id: str) -> Optional[DocumentChunk]:
        stmt = select(DocumentChunk).where(DocumentChunk.vector_id == vector_id)
        return self.db.scalars(stmt).first()


# ---------------------------------------------------------------------------
# ResearchSessionRepository
# ---------------------------------------------------------------------------


class ResearchSessionRepository(BaseRepository[ResearchSession]):
    model = ResearchSession

    def get_by_user(
        self, user_id: str, limit: int = 50, offset: int = 0
    ) -> List[ResearchSession]:
        stmt = (
            select(ResearchSession)
            .where(ResearchSession.user_id == user_id)
            .order_by(ResearchSession.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(stmt).all())

    def list_by_status(
        self, status: SessionStatus | str, limit: int = 100, offset: int = 0
    ) -> List[ResearchSession]:
        status_value = status.value if isinstance(status, SessionStatus) else status
        stmt = (
            select(ResearchSession)
            .where(ResearchSession.status == status_value)
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(stmt).all())

    def mark_completed(
        self,
        id: str,
        answer: str,
        citations: list[str],
        metadata: dict[str, Any],
        duration_ms: int | None = None,
    ) -> Optional[ResearchSession]:
        import json
        from datetime import datetime, timezone

        obj = self.get(id)
        if obj is None:
            return None
        obj.status = SessionStatus.completed.value
        obj.answer = answer
        obj.citations_json = json.dumps(citations)
        obj.metadata_json = json.dumps(metadata)
        obj.duration_ms = duration_ms
        obj.completed_at = datetime.now(timezone.utc).isoformat()
        self.db.flush()
        return obj

    def mark_failed(self, id: str, error: str) -> Optional[ResearchSession]:
        from datetime import datetime, timezone

        obj = self.get(id)
        if obj is None:
            return None
        obj.status = SessionStatus.failed.value
        obj.error_message = error
        obj.completed_at = datetime.now(timezone.utc).isoformat()
        self.db.flush()
        return obj


# ---------------------------------------------------------------------------
# ResearchSubQuestionRepository
# ---------------------------------------------------------------------------


class ResearchSubQuestionRepository(BaseRepository[ResearchSubQuestion]):
    model = ResearchSubQuestion

    def get_by_session(self, session_id: str) -> List[ResearchSubQuestion]:
        stmt = (
            select(ResearchSubQuestion)
            .where(ResearchSubQuestion.session_id == session_id)
            .order_by(ResearchSubQuestion.position)
        )
        return list(self.db.scalars(stmt).all())


# ---------------------------------------------------------------------------
# WorkflowEventRepository
# ---------------------------------------------------------------------------


class WorkflowEventRepository(BaseRepository[WorkflowEvent]):
    model = WorkflowEvent

    def get_by_session(self, session_id: str) -> List[WorkflowEvent]:
        stmt = (
            select(WorkflowEvent)
            .where(WorkflowEvent.session_id == session_id)
            .order_by(WorkflowEvent.created_at)
        )
        return list(self.db.scalars(stmt).all())

    def append_event(
        self,
        session_id: str,
        event_type: str,
        node_name: str | None = None,
        payload: dict[str, Any] | None = None,
        duration_ms: int | None = None,
    ) -> WorkflowEvent:
        import json

        return self.create(
            session_id=session_id,
            event_type=event_type,
            node_name=node_name,
            payload_json=json.dumps(payload or {}),
            duration_ms=duration_ms,
        )


# ---------------------------------------------------------------------------
# AuditLogRepository
# ---------------------------------------------------------------------------


class AuditLogRepository(BaseRepository[AuditLog]):
    model = AuditLog

    def log(
        self,
        action: str,
        user_id: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        detail: dict[str, Any] | None = None,
        ip_address: str | None = None,
        request_id: str | None = None,
    ) -> AuditLog:
        import json

        return self.create(
            action=action,
            user_id=user_id,
            target_type=target_type,
            target_id=target_id,
            detail_json=json.dumps(detail or {}),
            ip_address=ip_address,
            request_id=request_id,
        )

    def get_by_target(self, target_type: str, target_id: str) -> List[AuditLog]:
        stmt = (
            select(AuditLog)
            .where(AuditLog.target_type == target_type, AuditLog.target_id == target_id)
            .order_by(AuditLog.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def get_by_user(self, user_id: str, limit: int = 100) -> List[AuditLog]:
        stmt = (
            select(AuditLog)
            .where(AuditLog.user_id == user_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())


# ---------------------------------------------------------------------------
# ProcessTemplateRepository
# ---------------------------------------------------------------------------


class ProcessTemplateRepository(BaseRepository[ProcessTemplate]):
    model = ProcessTemplate

    def get_by_name(self, name: str) -> Optional[ProcessTemplate]:
        stmt = select(ProcessTemplate).where(ProcessTemplate.name == name)
        return self.db.scalars(stmt).first()

    def list_active(self) -> List[ProcessTemplate]:
        stmt = select(ProcessTemplate).where(ProcessTemplate.is_active.is_(True))
        return list(self.db.scalars(stmt).all())


# ---------------------------------------------------------------------------
# ProcessInstanceRepository
# ---------------------------------------------------------------------------


class ProcessInstanceRepository(BaseRepository[ProcessInstance]):
    model = ProcessInstance

    def get_by_template(self, template_id: str) -> List[ProcessInstance]:
        stmt = select(ProcessInstance).where(ProcessInstance.template_id == template_id)
        return list(self.db.scalars(stmt).all())

    def list_by_status(
        self, status: ProcessStatus | str, limit: int = 100, offset: int = 0
    ) -> List[ProcessInstance]:
        from .models.enums import ProcessStatus as PS
        status_value = status.value if isinstance(status, PS) else status
        stmt = (
            select(ProcessInstance)
            .where(ProcessInstance.status == status_value)
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(stmt).all())


# ---------------------------------------------------------------------------
# ProcessTaskRepository
# ---------------------------------------------------------------------------


class ProcessTaskRepository(BaseRepository[ProcessTask]):
    model = ProcessTask

    def get_by_instance(self, instance_id: str) -> List[ProcessTask]:
        stmt = (
            select(ProcessTask)
            .where(ProcessTask.instance_id == instance_id)
            .order_by(ProcessTask.position)
        )
        return list(self.db.scalars(stmt).all())


# ---------------------------------------------------------------------------
# ApprovalRequestRepository
# ---------------------------------------------------------------------------


class ApprovalRequestRepository(BaseRepository[ApprovalRequest]):
    model = ApprovalRequest

    def list_pending(self, limit: int = 50) -> List[ApprovalRequest]:
        stmt = (
            select(ApprovalRequest)
            .where(ApprovalRequest.status == ApprovalStatus.pending.value)
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())

    def get_by_target(self, target_type: str, target_id: str) -> List[ApprovalRequest]:
        stmt = (
            select(ApprovalRequest)
            .where(
                ApprovalRequest.target_type == target_type,
                ApprovalRequest.target_id == target_id,
            )
        )
        return list(self.db.scalars(stmt).all())

    def decide(
        self,
        id: str,
        status: ApprovalStatus | str,
        decided_by_id: str,
        note: str | None = None,
    ) -> Optional[ApprovalRequest]:
        status_value = (
            status.value if isinstance(status, ApprovalStatus) else status
        )
        return self.update(
            id,
            status=status_value,
            decided_by_id=decided_by_id,
            decision_note=note,
        )
