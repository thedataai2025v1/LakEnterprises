"""Integration tests for P2-2 (DB) + P2-3 (Repository layer).

Uses an in-memory SQLite database (no file I/O) so tests are:
- Fast (no network, no disk)
- Isolated (each test class gets a fresh DB)
- Repeatable (no shared state across runs)

Covers:
- Table creation and schema constraints.
- Full CRUD for all repositories.
- Domain-specific repository methods (get_by_email, list_by_status, etc.).
- Relationship traversal (user→sessions, document→chunks, etc.).
- Soft-delete.
- mark_completed / mark_failed on ResearchSession.
- ApprovalRequest decide().
"""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy.orm import Session

from lakenterprises.db import (
    create_all_tables,
    drop_all_tables,
    make_session_factory,
    make_test_engine,
)
from lakenterprises.models import (
    ApprovalStatus,
    AuditAction,
    Document,
    DocumentChunk,
    DocumentStatus,
    DocumentType,
    ProcessInstance,
    ProcessStatus,
    ProcessTask,
    ProcessTemplate,
    ResearchSession,
    ResearchSubQuestion,
    SessionStatus,
    TaskStatus,
    User,
    UserRole,
    UserStatus,
    WorkflowEvent,
)
from lakenterprises.models.enums import EventType, RetrievalStrategy
from lakenterprises.repositories import (
    ApprovalRequestRepository,
    AuditLogRepository,
    DocumentChunkRepository,
    DocumentRepository,
    ProcessInstanceRepository,
    ProcessTaskRepository,
    ProcessTemplateRepository,
    ResearchSessionRepository,
    ResearchSubQuestionRepository,
    UserRepository,
    WorkflowEventRepository,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="class")
def engine():
    """In-memory SQLite engine per test class."""
    eng = make_test_engine()
    create_all_tables(eng)
    yield eng
    drop_all_tables(eng)
    eng.dispose()


@pytest.fixture(scope="class")
def db(engine):
    """Shared session for the class; rolls back after all tests in the class."""
    factory = make_session_factory(engine)
    session = factory()
    yield session
    session.rollback()
    session.close()


@pytest.fixture(scope="function")
def fresh_db(engine):
    """Per-function session that always rolls back (true isolation)."""
    factory = make_session_factory(engine)
    session = factory()
    yield session
    session.rollback()
    session.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(db: Session, email: str = None, role: str = UserRole.viewer.value) -> User:
    email = email or f"{uuid.uuid4()}@test.com"
    user = User(
        email=email,
        full_name="Test User",
        hashed_password="hashed",
        role=role,
    )
    db.add(user)
    db.flush()
    return user


def _make_document(db: Session, uploader_id: str, status: str = DocumentStatus.pending.value) -> Document:
    doc = Document(
        filename=f"doc_{uuid.uuid4()}.md",
        original_filename="original.md",
        uploader_id=uploader_id,
        status=status,
        doc_type=DocumentType.markdown.value,
    )
    db.add(doc)
    db.flush()
    return doc


def _make_session(db: Session, user_id: str) -> ResearchSession:
    session = ResearchSession(
        user_id=user_id,
        question="What is GDPR?",
        status=SessionStatus.running.value,
    )
    db.add(session)
    db.flush()
    return session


def _make_template(db: Session, name: str = None) -> ProcessTemplate:
    name = name or f"Template-{uuid.uuid4()}"
    tmpl = ProcessTemplate(name=name, definition_json=json.dumps({"steps": []}))
    db.add(tmpl)
    db.flush()
    return tmpl


# ---------------------------------------------------------------------------
# DB / Schema tests
# ---------------------------------------------------------------------------


class TestDatabaseSchema:
    """Verify that the schema is created correctly."""

    def test_all_tables_created(self, engine):
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        expected = {
            "users",
            "documents",
            "document_chunks",
            "research_sessions",
            "research_sub_questions",
            "workflow_events",
            "audit_log",
            "process_templates",
            "process_instances",
            "process_tasks",
            "approval_requests",
        }
        assert expected.issubset(tables)

    def test_users_table_has_email_unique(self, engine):
        from sqlalchemy import inspect
        inspector = inspect(engine)
        indexes = inspector.get_indexes("users")
        unique_columns = {
            col
            for idx in indexes
            for col in idx["column_names"]
            if idx.get("unique")
        }
        assert "email" in unique_columns

    def test_document_chunks_unique_constraint(self, engine):
        from sqlalchemy import inspect
        inspector = inspect(engine)
        constraints = inspector.get_unique_constraints("document_chunks")
        names = [c["name"] for c in constraints]
        assert "uq_chunk_per_doc" in names

    def test_create_all_idempotent(self, engine):
        """Calling create_all_tables twice must not raise."""
        create_all_tables(engine)  # second call


# ---------------------------------------------------------------------------
# UserRepository
# ---------------------------------------------------------------------------


class TestUserRepository:
    def test_create_and_get(self, fresh_db):
        repo = UserRepository(fresh_db)
        user = repo.create(
            email="alice@example.com",
            full_name="Alice",
            hashed_password="h",
            role=UserRole.analyst.value,
        )
        assert user.id is not None
        fetched = repo.get(user.id)
        assert fetched is not None
        assert fetched.email == "alice@example.com"

    def test_get_by_email(self, fresh_db):
        repo = UserRepository(fresh_db)
        repo.create(email="bob@example.com", full_name="Bob", hashed_password="h")
        result = repo.get_by_email("bob@example.com")
        assert result is not None
        assert result.full_name == "Bob"

    def test_get_by_email_not_found(self, fresh_db):
        repo = UserRepository(fresh_db)
        assert repo.get_by_email("nobody@example.com") is None

    def test_get_by_role(self, fresh_db):
        repo = UserRepository(fresh_db)
        repo.create(email="admin1@x.com", full_name="A", hashed_password="h", role=UserRole.admin.value)
        repo.create(email="admin2@x.com", full_name="B", hashed_password="h", role=UserRole.admin.value)
        admins = repo.get_by_role(UserRole.admin)
        assert len(admins) >= 2

    def test_email_exists(self, fresh_db):
        repo = UserRepository(fresh_db)
        repo.create(email="charlie@x.com", full_name="C", hashed_password="h")
        assert repo.email_exists("charlie@x.com") is True
        assert repo.email_exists("nobody@x.com") is False

    def test_update(self, fresh_db):
        repo = UserRepository(fresh_db)
        user = repo.create(email="dave@x.com", full_name="Dave", hashed_password="h")
        updated = repo.update(user.id, full_name="David")
        assert updated.full_name == "David"

    def test_delete(self, fresh_db):
        repo = UserRepository(fresh_db)
        user = repo.create(email="eve@x.com", full_name="Eve", hashed_password="h")
        result = repo.delete(user.id)
        assert result is True
        assert repo.get(user.id) is None

    def test_get_or_raise_raises_on_missing(self, fresh_db):
        repo = UserRepository(fresh_db)
        with pytest.raises(KeyError):
            repo.get_or_raise("non-existent-id")

    def test_count(self, fresh_db):
        repo = UserRepository(fresh_db)
        before = repo.count()
        repo.create(email="frank@x.com", full_name="Frank", hashed_password="h")
        assert repo.count() == before + 1

    def test_list_active(self, fresh_db):
        repo = UserRepository(fresh_db)
        repo.create(email="g@x.com", full_name="G", hashed_password="h", status=UserStatus.active.value)
        repo.create(email="h@x.com", full_name="H", hashed_password="h", status=UserStatus.inactive.value)
        active = repo.list_active()
        statuses = {u.status for u in active}
        assert "inactive" not in statuses


# ---------------------------------------------------------------------------
# DocumentRepository
# ---------------------------------------------------------------------------


class TestDocumentRepository:
    def test_create_document(self, fresh_db):
        user = _make_user(fresh_db)
        repo = DocumentRepository(fresh_db)
        doc = repo.create(
            filename="test.md",
            original_filename="test.md",
            uploader_id=user.id,
        )
        assert doc.id is not None
        assert doc.status == DocumentStatus.pending.value

    def test_soft_delete(self, fresh_db):
        user = _make_user(fresh_db)
        repo = DocumentRepository(fresh_db)
        doc = repo.create(filename="del.md", original_filename="del.md", uploader_id=user.id)
        result = repo.soft_delete(doc.id)
        assert result.status == DocumentStatus.deleted.value

    def test_set_status(self, fresh_db):
        user = _make_user(fresh_db)
        repo = DocumentRepository(fresh_db)
        doc = repo.create(filename="idx.md", original_filename="idx.md", uploader_id=user.id)
        updated = repo.set_status(doc.id, DocumentStatus.indexed)
        assert updated.status == DocumentStatus.indexed.value

    def test_list_by_status(self, fresh_db):
        user = _make_user(fresh_db)
        repo = DocumentRepository(fresh_db)
        repo.create(filename="p1.md", original_filename="p1.md", uploader_id=user.id, status=DocumentStatus.indexed.value)
        repo.create(filename="p2.md", original_filename="p2.md", uploader_id=user.id, status=DocumentStatus.indexed.value)
        indexed = repo.list_by_status(DocumentStatus.indexed)
        assert all(d.status == DocumentStatus.indexed.value for d in indexed)
        assert len(indexed) >= 2

    def test_get_by_uploader(self, fresh_db):
        user = _make_user(fresh_db)
        other = _make_user(fresh_db)
        repo = DocumentRepository(fresh_db)
        repo.create(filename="u1.md", original_filename="u1.md", uploader_id=user.id)
        repo.create(filename="u2.md", original_filename="u2.md", uploader_id=user.id)
        repo.create(filename="o1.md", original_filename="o1.md", uploader_id=other.id)
        docs = repo.get_by_uploader(user.id)
        assert all(d.uploader_id == user.id for d in docs)
        assert len(docs) >= 2

    def test_increment_chunk_count(self, fresh_db):
        user = _make_user(fresh_db)
        repo = DocumentRepository(fresh_db)
        doc = repo.create(filename="chunks.md", original_filename="chunks.md", uploader_id=user.id)
        assert doc.chunk_count == 0
        repo.increment_chunk_count(doc.id, 5)
        assert repo.get(doc.id).chunk_count == 5


# ---------------------------------------------------------------------------
# DocumentChunkRepository
# ---------------------------------------------------------------------------


class TestDocumentChunkRepository:
    def test_create_and_get_by_document(self, fresh_db):
        user = _make_user(fresh_db)
        doc = _make_document(fresh_db, user.id)
        repo = DocumentChunkRepository(fresh_db)
        for i in range(3):
            repo.create(document_id=doc.id, chunk_index=i, content=f"Chunk {i}")
        chunks = repo.get_by_document(doc.id)
        assert len(chunks) == 3
        assert [c.chunk_index for c in chunks] == [0, 1, 2]

    def test_delete_by_document(self, fresh_db):
        user = _make_user(fresh_db)
        doc = _make_document(fresh_db, user.id)
        repo = DocumentChunkRepository(fresh_db)
        for i in range(2):
            repo.create(document_id=doc.id, chunk_index=i, content=f"C{i}")
        deleted = repo.delete_by_document(doc.id)
        assert deleted == 2
        assert repo.get_by_document(doc.id) == []

    def test_get_by_vector_id(self, fresh_db):
        user = _make_user(fresh_db)
        doc = _make_document(fresh_db, user.id)
        repo = DocumentChunkRepository(fresh_db)
        vid = str(uuid.uuid4())
        chunk = repo.create(document_id=doc.id, chunk_index=0, content="text", vector_id=vid)
        found = repo.get_by_vector_id(vid)
        assert found is not None
        assert found.id == chunk.id


# ---------------------------------------------------------------------------
# ResearchSessionRepository
# ---------------------------------------------------------------------------


class TestResearchSessionRepository:
    def test_create_session(self, fresh_db):
        user = _make_user(fresh_db)
        repo = ResearchSessionRepository(fresh_db)
        session = repo.create(user_id=user.id, question="Test question?")
        assert session.status == SessionStatus.running.value

    def test_mark_completed(self, fresh_db):
        user = _make_user(fresh_db)
        repo = ResearchSessionRepository(fresh_db)
        session = repo.create(user_id=user.id, question="GDPR?")
        updated = repo.mark_completed(
            session.id,
            answer="GDPR stands for…",
            citations=["[doc1]"],
            metadata={"run_id": "abc"},
            duration_ms=1234,
        )
        assert updated.status == SessionStatus.completed.value
        assert updated.answer == "GDPR stands for…"
        assert updated.citations == ["[doc1]"]
        assert updated.duration_ms == 1234

    def test_mark_failed(self, fresh_db):
        user = _make_user(fresh_db)
        repo = ResearchSessionRepository(fresh_db)
        session = repo.create(user_id=user.id, question="Q?")
        updated = repo.mark_failed(session.id, error="LLM timeout")
        assert updated.status == SessionStatus.failed.value
        assert updated.error_message == "LLM timeout"

    def test_get_by_user(self, fresh_db):
        user = _make_user(fresh_db)
        other = _make_user(fresh_db)
        repo = ResearchSessionRepository(fresh_db)
        repo.create(user_id=user.id, question="Q1?")
        repo.create(user_id=user.id, question="Q2?")
        repo.create(user_id=other.id, question="O1?")
        sessions = repo.get_by_user(user.id)
        assert all(s.user_id == user.id for s in sessions)
        assert len(sessions) >= 2

    def test_list_by_status(self, fresh_db):
        user = _make_user(fresh_db)
        repo = ResearchSessionRepository(fresh_db)
        repo.create(user_id=user.id, question="A?", status=SessionStatus.completed.value)
        repo.create(user_id=user.id, question="B?", status=SessionStatus.running.value)
        completed = repo.list_by_status(SessionStatus.completed)
        assert all(s.status == SessionStatus.completed.value for s in completed)


# ---------------------------------------------------------------------------
# WorkflowEventRepository
# ---------------------------------------------------------------------------


class TestWorkflowEventRepository:
    def test_append_and_get_by_session(self, fresh_db):
        user = _make_user(fresh_db)
        session = _make_session(fresh_db, user.id)
        repo = WorkflowEventRepository(fresh_db)
        repo.append_event(session.id, EventType.node_start.value, node_name="analyze")
        repo.append_event(session.id, EventType.node_end.value, node_name="analyze", duration_ms=100)
        events = repo.get_by_session(session.id)
        assert len(events) == 2
        assert events[0].node_name == "analyze"

    def test_payload_stored_correctly(self, fresh_db):
        user = _make_user(fresh_db)
        session = _make_session(fresh_db, user.id)
        repo = WorkflowEventRepository(fresh_db)
        payload = {"query": "test", "num_docs": 5}
        ev = repo.append_event(session.id, EventType.retrieval.value, payload=payload)
        assert ev.payload["query"] == "test"


# ---------------------------------------------------------------------------
# AuditLogRepository
# ---------------------------------------------------------------------------


class TestAuditLogRepository:
    def test_log_action(self, fresh_db):
        user = _make_user(fresh_db)
        repo = AuditLogRepository(fresh_db)
        log = repo.log(
            action=AuditAction.login.value,
            user_id=user.id,
            detail={"ip": "10.0.0.1"},
        )
        assert log.id is not None
        assert log.action == AuditAction.login.value

    def test_get_by_user(self, fresh_db):
        user = _make_user(fresh_db)
        repo = AuditLogRepository(fresh_db)
        repo.log(action="login", user_id=user.id)
        repo.log(action="read", user_id=user.id)
        entries = repo.get_by_user(user.id)
        assert len(entries) >= 2
        assert all(e.user_id == user.id for e in entries)

    def test_get_by_target(self, fresh_db):
        user = _make_user(fresh_db)
        doc_id = str(uuid.uuid4())
        repo = AuditLogRepository(fresh_db)
        repo.log(action="delete", target_type="document", target_id=doc_id)
        entries = repo.get_by_target("document", doc_id)
        assert len(entries) == 1
        assert entries[0].target_id == doc_id


# ---------------------------------------------------------------------------
# ProcessTemplateRepository
# ---------------------------------------------------------------------------


class TestProcessTemplateRepository:
    def test_create_and_get_by_name(self, fresh_db):
        repo = ProcessTemplateRepository(fresh_db)
        tmpl = repo.create(name="Invoice Approval", definition_json=json.dumps({"steps": []}))
        found = repo.get_by_name("Invoice Approval")
        assert found is not None
        assert found.id == tmpl.id

    def test_list_active(self, fresh_db):
        repo = ProcessTemplateRepository(fresh_db)
        repo.create(name="Active Template", is_active=True)
        repo.create(name="Inactive Template", is_active=False)
        active = repo.list_active()
        assert all(t.is_active for t in active)


# ---------------------------------------------------------------------------
# ProcessInstanceRepository
# ---------------------------------------------------------------------------


class TestProcessInstanceRepository:
    def test_create_instance(self, fresh_db):
        user = _make_user(fresh_db)
        tmpl = _make_template(fresh_db)
        repo = ProcessInstanceRepository(fresh_db)
        instance = repo.create(
            template_id=tmpl.id,
            initiated_by_id=user.id,
            title="Test Instance",
        )
        assert instance.status == ProcessStatus.active.value

    def test_list_by_status(self, fresh_db):
        user = _make_user(fresh_db)
        tmpl = _make_template(fresh_db)
        repo = ProcessInstanceRepository(fresh_db)
        repo.create(template_id=tmpl.id, initiated_by_id=user.id, title="A", status=ProcessStatus.active.value)
        repo.create(template_id=tmpl.id, initiated_by_id=user.id, title="B", status=ProcessStatus.completed.value)
        active = repo.list_by_status(ProcessStatus.active)
        assert all(i.status == ProcessStatus.active.value for i in active)


# ---------------------------------------------------------------------------
# ApprovalRequestRepository
# ---------------------------------------------------------------------------


class TestApprovalRequestRepository:
    def test_create_and_list_pending(self, fresh_db):
        user = _make_user(fresh_db)
        repo = ApprovalRequestRepository(fresh_db)
        req = repo.create(
            target_type="document",
            target_id=str(uuid.uuid4()),
            action="delete",
            requested_by_id=user.id,
        )
        pending = repo.list_pending()
        assert any(p.id == req.id for p in pending)

    def test_decide_approve(self, fresh_db):
        requester = _make_user(fresh_db)
        decider = _make_user(fresh_db, role=UserRole.admin.value)
        repo = ApprovalRequestRepository(fresh_db)
        req = repo.create(
            target_type="document",
            target_id=str(uuid.uuid4()),
            action="delete",
            requested_by_id=requester.id,
        )
        updated = repo.decide(req.id, ApprovalStatus.approved, decider.id, note="Looks good")
        assert updated.status == ApprovalStatus.approved.value
        assert updated.decided_by_id == decider.id
        assert updated.decision_note == "Looks good"

    def test_decide_reject(self, fresh_db):
        requester = _make_user(fresh_db)
        decider = _make_user(fresh_db, role=UserRole.admin.value)
        repo = ApprovalRequestRepository(fresh_db)
        req = repo.create(
            target_type="document",
            target_id=str(uuid.uuid4()),
            action="delete",
            requested_by_id=requester.id,
        )
        updated = repo.decide(req.id, ApprovalStatus.rejected, decider.id)
        assert updated.status == ApprovalStatus.rejected.value

    def test_get_by_target(self, fresh_db):
        requester = _make_user(fresh_db)
        repo = ApprovalRequestRepository(fresh_db)
        tid = str(uuid.uuid4())
        repo.create(target_type="document", target_id=tid, action="delete", requested_by_id=requester.id)
        found = repo.get_by_target("document", tid)
        assert len(found) == 1
        assert found[0].target_id == tid


# ---------------------------------------------------------------------------
# Relationship traversal tests
# ---------------------------------------------------------------------------


class TestRelationships:
    def test_user_sessions_relationship(self, fresh_db):
        user = _make_user(fresh_db)
        session1 = _make_session(fresh_db, user.id)
        session2 = _make_session(fresh_db, user.id)
        fresh_db.refresh(user)
        assert len(user.research_sessions) == 2

    def test_document_chunks_relationship(self, fresh_db):
        user = _make_user(fresh_db)
        doc = _make_document(fresh_db, user.id)
        for i in range(3):
            chunk = DocumentChunk(document_id=doc.id, chunk_index=i, content=f"C{i}")
            fresh_db.add(chunk)
        fresh_db.flush()
        fresh_db.refresh(doc)
        assert len(doc.chunks) == 3

    def test_session_sub_questions_relationship(self, fresh_db):
        user = _make_user(fresh_db)
        session = _make_session(fresh_db, user.id)
        for i in range(2):
            sq = ResearchSubQuestion(
                session_id=session.id,
                position=i,
                question=f"Sub {i}?",
            )
            fresh_db.add(sq)
        fresh_db.flush()
        fresh_db.refresh(session)
        assert len(session.sub_questions) == 2

    def test_process_template_instances_relationship(self, fresh_db):
        user = _make_user(fresh_db)
        tmpl = _make_template(fresh_db)
        inst = ProcessInstance(template_id=tmpl.id, initiated_by_id=user.id, title="Inst")
        fresh_db.add(inst)
        fresh_db.flush()
        fresh_db.refresh(tmpl)
        assert len(tmpl.instances) == 1
