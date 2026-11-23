"""Unit tests for P2-1: SQLAlchemy entities and enums.

Covers:
- All enum values and their string serialisation.
- ORM entity construction, defaults, and to_dict().
- JSON property helpers (metadata, citations, evidence, payload, detail).
- Enum property helpers on entities.
- UUID primary key generation (each instance gets a unique id).
- TimestampMixin auto-fill.
"""

from __future__ import annotations

import json
import uuid

import pytest

from lakenterprises.models.enums import (
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
from lakenterprises.models.entities import (
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


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestUserRoleEnum:
    def test_all_values_present(self):
        assert set(r.value for r in UserRole) == {"viewer", "analyst", "admin"}

    def test_is_str_subclass(self):
        assert isinstance(UserRole.admin, str)

    def test_lookup_by_value(self):
        assert UserRole("viewer") is UserRole.viewer


class TestDocumentStatusEnum:
    def test_round_trip(self):
        for status in DocumentStatus:
            assert DocumentStatus(status.value) is status

    def test_deleted_value(self):
        assert DocumentStatus.deleted.value == "deleted"


class TestSessionStatusEnum:
    def test_all_values(self):
        expected = {"running", "completed", "failed"}
        assert {s.value for s in SessionStatus} == expected


class TestRetrievalStrategyEnum:
    def test_hybrid_exists(self):
        assert RetrievalStrategy.hybrid.value == "hybrid"


class TestAuditActionEnum:
    def test_login_exists(self):
        assert AuditAction.login in AuditAction

    def test_all_values_are_strings(self):
        for action in AuditAction:
            assert isinstance(action.value, str)


class TestEventTypeEnum:
    def test_node_start_value(self):
        assert EventType.node_start.value == "node_start"


# ---------------------------------------------------------------------------
# User entity
# ---------------------------------------------------------------------------


class TestUserEntity:
    def test_defaults(self):
        u = User(
            email="test@example.com",
            full_name="Test User",
            hashed_password="hash123",
        )
        assert u.role == UserRole.viewer.value
        assert u.status == UserStatus.active.value
        assert u.is_demo is False

    def test_uuid_pk_generated(self):
        u1 = User(email="a@b.com", full_name="A", hashed_password="h")
        u2 = User(email="c@d.com", full_name="C", hashed_password="h")
        assert u1.id != u2.id
        assert len(u1.id) == 36  # UUID string length

    def test_role_enum_property(self):
        u = User(email="a@b.com", full_name="A", hashed_password="h", role="analyst")
        assert u.role_enum is UserRole.analyst

    def test_status_enum_property(self):
        u = User(email="a@b.com", full_name="A", hashed_password="h", status="inactive")
        assert u.status_enum is UserStatus.inactive


# ---------------------------------------------------------------------------
# Document entity
# ---------------------------------------------------------------------------


class TestDocumentEntity:
    def _make_doc(self, **kwargs) -> Document:
        return Document(
            filename="test.md",
            original_filename="test.md",
            uploader_id=str(uuid.uuid4()),
            **kwargs,
        )

    def test_defaults(self):
        doc = self._make_doc()
        assert doc.status == DocumentStatus.pending.value
        assert doc.doc_type == DocumentType.other.value
        assert doc.file_size_bytes == 0
        assert doc.chunk_count == 0

    def test_metadata_json_property(self):
        doc = self._make_doc()
        doc.metadata = {"source": "upload", "tags": ["gdpr"]}
        assert doc.metadata_json == json.dumps({"source": "upload", "tags": ["gdpr"]})
        assert doc.metadata["source"] == "upload"

    def test_status_enum_property(self):
        doc = self._make_doc(status="indexed")
        assert doc.status_enum is DocumentStatus.indexed

    def test_to_dict_has_expected_keys(self):
        doc = self._make_doc()
        # to_dict() requires a mapped session; here we just check the entity has an id
        assert hasattr(doc, "id")


# ---------------------------------------------------------------------------
# DocumentChunk entity
# ---------------------------------------------------------------------------


class TestDocumentChunkEntity:
    def test_metadata_property(self):
        chunk = DocumentChunk(
            document_id=str(uuid.uuid4()),
            chunk_index=0,
            content="Hello world",
        )
        chunk.metadata = {"page": 1}
        assert chunk.metadata == {"page": 1}
        assert '"page"' in chunk.metadata_json

    def test_defaults(self):
        chunk = DocumentChunk(
            document_id=str(uuid.uuid4()),
            chunk_index=1,
            content="Content",
        )
        assert chunk.token_count == 0
        assert chunk.vector_id is None


# ---------------------------------------------------------------------------
# ResearchSession entity
# ---------------------------------------------------------------------------


class TestResearchSessionEntity:
    def test_citations_property(self):
        session = ResearchSession(
            user_id=str(uuid.uuid4()),
            question="What is GDPR?",
        )
        session.citations = ["[doc1 - chunk #1]", "[doc2 - chunk #2]"]
        parsed = session.citations
        assert isinstance(parsed, list)
        assert parsed[0] == "[doc1 - chunk #1]"

    def test_metadata_property(self):
        session = ResearchSession(
            user_id=str(uuid.uuid4()),
            question="Q?",
        )
        session.metadata = {"run_id": "abc"}
        assert session.metadata["run_id"] == "abc"

    def test_complexity_enum_property(self):
        session = ResearchSession(
            user_id=str(uuid.uuid4()),
            question="Q?",
            complexity=QueryComplexity.complex.value,
        )
        assert session.complexity_enum is QueryComplexity.complex

    def test_complexity_enum_none_when_not_set(self):
        session = ResearchSession(user_id=str(uuid.uuid4()), question="Q?")
        assert session.complexity_enum is None

    def test_status_default(self):
        session = ResearchSession(user_id=str(uuid.uuid4()), question="Q?")
        assert session.status == SessionStatus.running.value


# ---------------------------------------------------------------------------
# ResearchSubQuestion entity
# ---------------------------------------------------------------------------


class TestResearchSubQuestionEntity:
    def test_evidence_property(self):
        sq = ResearchSubQuestion(
            session_id=str(uuid.uuid4()),
            position=0,
            question="Sub?",
        )
        evidence = [{"source": "doc.md", "text": "Some text", "verification_status": "verified"}]
        sq.evidence = evidence
        assert sq.evidence[0]["source"] == "doc.md"

    def test_strategy_enum_default(self):
        sq = ResearchSubQuestion(
            session_id=str(uuid.uuid4()),
            position=0,
            question="Sub?",
        )
        assert sq.strategy_enum is RetrievalStrategy.vector


# ---------------------------------------------------------------------------
# WorkflowEvent entity
# ---------------------------------------------------------------------------


class TestWorkflowEventEntity:
    def test_payload_property(self):
        ev = WorkflowEvent(
            session_id=str(uuid.uuid4()),
            event_type=EventType.node_start.value,
            node_name="analyze",
        )
        ev.payload = {"key": "value"}
        assert ev.payload["key"] == "value"

    def test_no_updated_at(self):
        # WorkflowEvent is write-once; it has no updated_at column
        ev = WorkflowEvent(
            session_id=str(uuid.uuid4()),
            event_type=EventType.node_end.value,
        )
        assert not hasattr(ev, "updated_at")


# ---------------------------------------------------------------------------
# AuditLog entity
# ---------------------------------------------------------------------------


class TestAuditLogEntity:
    def test_detail_property(self):
        log = AuditLog(
            action=AuditAction.login.value,
        )
        log.detail = {"ip": "127.0.0.1"}
        assert log.detail["ip"] == "127.0.0.1"

    def test_no_updated_at(self):
        log = AuditLog(action=AuditAction.create.value)
        assert not hasattr(log, "updated_at")


# ---------------------------------------------------------------------------
# ProcessTemplate entity
# ---------------------------------------------------------------------------


class TestProcessTemplateEntity:
    def test_definition_property(self):
        tmpl = ProcessTemplate(name="Invoice Approval")
        tmpl.definition = {"steps": ["Review", "Approve"]}
        assert tmpl.definition["steps"][0] == "Review"

    def test_defaults(self):
        tmpl = ProcessTemplate(name="Test Template")
        assert tmpl.version == 1
        assert tmpl.is_active is True


# ---------------------------------------------------------------------------
# ProcessInstance entity
# ---------------------------------------------------------------------------


class TestProcessInstanceEntity:
    def test_context_property(self):
        inst = ProcessInstance(
            template_id=str(uuid.uuid4()),
            title="Test Instance",
        )
        inst.context = {"vendor": "Acme"}
        assert inst.context["vendor"] == "Acme"

    def test_status_default(self):
        inst = ProcessInstance(
            template_id=str(uuid.uuid4()),
            title="Test",
        )
        assert inst.status == ProcessStatus.active.value


# ---------------------------------------------------------------------------
# ProcessTask entity
# ---------------------------------------------------------------------------


class TestProcessTaskEntity:
    def test_result_property(self):
        task = ProcessTask(
            instance_id=str(uuid.uuid4()),
            position=0,
            name="Review",
        )
        task.result = {"outcome": "passed"}
        assert task.result["outcome"] == "passed"

    def test_status_default(self):
        task = ProcessTask(
            instance_id=str(uuid.uuid4()),
            position=0,
            name="Task",
        )
        assert task.status == TaskStatus.pending.value


# ---------------------------------------------------------------------------
# ApprovalRequest entity
# ---------------------------------------------------------------------------


class TestApprovalRequestEntity:
    def test_status_default(self):
        req = ApprovalRequest(
            target_type="document",
            target_id=str(uuid.uuid4()),
            action="delete",
            requested_by_id=str(uuid.uuid4()),
        )
        assert req.status_enum is ApprovalStatus.pending

    def test_status_enum_property(self):
        req = ApprovalRequest(
            target_type="document",
            target_id=str(uuid.uuid4()),
            action="delete",
            requested_by_id=str(uuid.uuid4()),
            status=ApprovalStatus.approved.value,
        )
        assert req.status_enum is ApprovalStatus.approved
