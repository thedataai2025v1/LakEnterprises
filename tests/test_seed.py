"""Integration tests for P2-4: seed data loader (bootstrap / demo fixtures).

Verifies that:
- run_seed() creates all expected tables and rows.
- Seed is idempotent (running twice does not duplicate rows).
- Demo users have the correct roles and statuses.
- Process templates, documents, chunks, and research sessions are present.
- The seeded research session has sub-questions and workflow events.
- The seeded process instance has tasks.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from lakenterprises.db import (
    create_all_tables,
    make_session_factory,
    make_test_engine,
)
from lakenterprises.models import (
    Document,
    DocumentChunk,
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
from lakenterprises.seed import (
    DEMO_DOCUMENTS,
    DEMO_TEMPLATES,
    DEMO_USERS,
    _do_seed,
    run_seed,
)


@pytest.fixture(scope="module")
def seeded_db():
    """Run the seed once and expose the session for all tests in the module."""
    eng = make_test_engine()
    create_all_tables(eng)
    factory = make_session_factory(eng)
    db = factory()
    _do_seed(db)
    db.commit()
    yield db
    db.close()
    eng.dispose()


class TestSeedUsers:
    def test_all_demo_users_created(self, seeded_db):
        users = seeded_db.scalars(select(User)).all()
        emails = {u.email for u in users}
        for data in DEMO_USERS:
            assert data["email"] in emails

    def test_roles_match_expected(self, seeded_db):
        users = seeded_db.scalars(select(User)).all()
        role_map = {u.email: u.role for u in users}
        assert role_map["viewer@lakenterprises.demo"] == UserRole.viewer.value
        assert role_map["analyst@lakenterprises.demo"] == UserRole.analyst.value
        assert role_map["admin@lakenterprises.demo"] == UserRole.admin.value

    def test_all_users_are_active(self, seeded_db):
        users = seeded_db.scalars(select(User)).all()
        demo_users = [u for u in users if u.is_demo]
        assert all(u.status == "active" for u in demo_users)

    def test_is_demo_flag_set(self, seeded_db):
        users = seeded_db.scalars(select(User)).all()
        assert all(u.is_demo for u in users)


class TestSeedProcessTemplates:
    def test_all_templates_created(self, seeded_db):
        templates = seeded_db.scalars(select(ProcessTemplate)).all()
        names = {t.name for t in templates}
        for data in DEMO_TEMPLATES:
            assert data["name"] in names

    def test_templates_are_active(self, seeded_db):
        templates = seeded_db.scalars(select(ProcessTemplate)).all()
        assert all(t.is_active for t in templates)

    def test_template_has_definition(self, seeded_db):
        tmpl = seeded_db.scalars(select(ProcessTemplate).limit(1)).first()
        assert tmpl is not None
        defn = tmpl.definition
        assert "steps" in defn


class TestSeedDocuments:
    def test_expected_documents_created(self, seeded_db):
        docs = seeded_db.scalars(select(Document)).all()
        filenames = {d.filename for d in docs}
        for data in DEMO_DOCUMENTS:
            assert data["filename"] in filenames

    def test_documents_are_indexed(self, seeded_db):
        docs = seeded_db.scalars(select(Document)).all()
        assert all(d.status == "indexed" for d in docs)

    def test_chunks_created(self, seeded_db):
        chunks = seeded_db.scalars(select(DocumentChunk)).all()
        expected_total = sum(len(d["chunks"]) for d in DEMO_DOCUMENTS)
        assert len(chunks) == expected_total

    def test_chunk_count_on_document(self, seeded_db):
        for doc_data in DEMO_DOCUMENTS:
            doc = seeded_db.scalars(
                select(Document).where(Document.filename == doc_data["filename"])
            ).first()
            assert doc is not None
            assert doc.chunk_count == len(doc_data["chunks"])

    def test_chunks_ordered_by_index(self, seeded_db):
        doc = seeded_db.scalars(select(Document).limit(1)).first()
        chunks = seeded_db.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == doc.id)
            .order_by(DocumentChunk.chunk_index)
        ).all()
        indices = [c.chunk_index for c in chunks]
        assert indices == sorted(indices)


class TestSeedResearchSession:
    def test_session_created(self, seeded_db):
        sessions = seeded_db.scalars(select(ResearchSession)).all()
        assert len(sessions) == 1

    def test_session_is_completed(self, seeded_db):
        session = seeded_db.scalars(select(ResearchSession)).first()
        assert session.status == SessionStatus.completed.value

    def test_session_has_answer(self, seeded_db):
        session = seeded_db.scalars(select(ResearchSession)).first()
        assert session.answer is not None
        assert len(session.answer) > 0

    def test_session_has_citations(self, seeded_db):
        session = seeded_db.scalars(select(ResearchSession)).first()
        citations = session.citations
        assert isinstance(citations, list)
        assert len(citations) > 0

    def test_session_has_sub_questions(self, seeded_db):
        session = seeded_db.scalars(select(ResearchSession)).first()
        sub_questions = seeded_db.scalars(
            select(ResearchSubQuestion).where(
                ResearchSubQuestion.session_id == session.id
            )
        ).all()
        assert len(sub_questions) >= 1

    def test_session_has_workflow_events(self, seeded_db):
        session = seeded_db.scalars(select(ResearchSession)).first()
        events = seeded_db.scalars(
            select(WorkflowEvent).where(WorkflowEvent.session_id == session.id)
        ).all()
        assert len(events) > 0

    def test_session_has_duration(self, seeded_db):
        session = seeded_db.scalars(select(ResearchSession)).first()
        assert session.duration_ms is not None
        assert session.duration_ms > 0


class TestSeedProcessInstance:
    def test_instance_created(self, seeded_db):
        instances = seeded_db.scalars(select(ProcessInstance)).all()
        assert len(instances) >= 1

    def test_instance_has_tasks(self, seeded_db):
        instance = seeded_db.scalars(select(ProcessInstance)).first()
        tasks = seeded_db.scalars(
            select(ProcessTask).where(ProcessTask.instance_id == instance.id)
        ).all()
        assert len(tasks) >= 1

    def test_first_task_is_in_progress(self, seeded_db):
        instance = seeded_db.scalars(select(ProcessInstance)).first()
        tasks = seeded_db.scalars(
            select(ProcessTask)
            .where(ProcessTask.instance_id == instance.id)
            .order_by(ProcessTask.position)
        ).all()
        assert tasks[0].status == "in_progress"


class TestSeedIdempotency:
    def test_seed_twice_no_duplicates(self):
        """Running the seed twice must not create duplicate users."""
        eng = make_test_engine()
        create_all_tables(eng)
        factory = make_session_factory(eng)

        db = factory()
        _do_seed(db)
        db.commit()

        # Second run
        _do_seed(db)
        db.commit()

        users = db.scalars(select(User)).all()
        emails = [u.email for u in users]
        # No duplicate emails
        assert len(emails) == len(set(emails))

        db.close()
        eng.dispose()
