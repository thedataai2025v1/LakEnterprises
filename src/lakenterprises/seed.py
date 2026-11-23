"""Bootstrap / seed data loader for the LakEnterprises demo.

Responsibilities
----------------
- Create all tables (idempotent).
- Insert demo users (viewer, analyst, admin) with known hashed passwords.
- Insert sample documents and their chunks.
- Insert sample process templates.
- Insert a sample research session and workflow events.

Design principles
-----------------
- **Idempotent** – every ``INSERT`` uses an *upsert* strategy so the loader
  can be called repeatedly without duplicating rows.
- **No real passwords** – demo hashes are deterministic SHA-256 digests,
  not bcrypt.  Phase 3 replaces these with proper hashing.
- **No external services** – pure SQLite writes.  Vector and graph stores
  are populated separately by the ingestion pipeline in Phase 4.

Usage
-----
    python -m lakenterprises.seed          # CLI
    from lakenterprises.seed import run_seed; run_seed()
"""

from __future__ import annotations

import hashlib
import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from .db import create_all_tables, db_session, make_engine, make_session_factory
from .models import (
    ApprovalRequest,
    ApprovalStatus,
    AuditAction,
    AuditLog,
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
from .models.enums import EventType, RetrievalStrategy, QueryComplexity

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_UTC = timezone.utc


def _now() -> str:
    return datetime.now(_UTC).isoformat()


def _hash_password(raw: str) -> str:
    """Deterministic SHA-256 hash – demo only, replaced by bcrypt in Phase 3."""
    return hashlib.sha256(raw.encode()).hexdigest()


def _upsert_user(db: Session, email: str, **kwargs: Any) -> User:
    from sqlalchemy import select

    stmt = select(User).where(User.email == email)
    existing = db.scalars(stmt).first()
    if existing:
        return existing
    user = User(email=email, **kwargs)
    db.add(user)
    db.flush()
    return user


def _upsert_template(db: Session, name: str, **kwargs: Any) -> ProcessTemplate:
    from sqlalchemy import select

    stmt = select(ProcessTemplate).where(ProcessTemplate.name == name)
    existing = db.scalars(stmt).first()
    if existing:
        return existing
    tmpl = ProcessTemplate(name=name, **kwargs)
    db.add(tmpl)
    db.flush()
    return tmpl


def _upsert_document(db: Session, filename: str, uploader_id: str, **kwargs: Any) -> Document:
    from sqlalchemy import select

    stmt = select(Document).where(
        Document.filename == filename, Document.uploader_id == uploader_id
    )
    existing = db.scalars(stmt).first()
    if existing:
        return existing
    doc = Document(filename=filename, uploader_id=uploader_id, **kwargs)
    db.add(doc)
    db.flush()
    return doc


# ---------------------------------------------------------------------------
# Demo users
# ---------------------------------------------------------------------------

DEMO_USERS: list[dict[str, Any]] = [
    {
        "email": "viewer@lakenterprises.demo",
        "full_name": "Demo Viewer",
        "hashed_password": _hash_password("viewer-pass-demo"),
        "role": UserRole.viewer.value,
        "status": UserStatus.active.value,
        "is_demo": True,
    },
    {
        "email": "analyst@lakenterprises.demo",
        "full_name": "Demo Analyst",
        "hashed_password": _hash_password("analyst-pass-demo"),
        "role": UserRole.analyst.value,
        "status": UserStatus.active.value,
        "is_demo": True,
    },
    {
        "email": "admin@lakenterprises.demo",
        "full_name": "Demo Admin",
        "hashed_password": _hash_password("admin-pass-demo"),
        "role": UserRole.admin.value,
        "status": UserStatus.active.value,
        "is_demo": True,
    },
]

# ---------------------------------------------------------------------------
# Demo process templates
# ---------------------------------------------------------------------------

DEMO_TEMPLATES: list[dict[str, Any]] = [
    {
        "name": "Invoice Approval",
        "description": "Standard two-step invoice review and payment approval workflow.",
        "version": 1,
        "is_active": True,
        "definition_json": json.dumps({
            "steps": [
                {"name": "Review Invoice", "requires_approval": False},
                {"name": "Finance Approval", "requires_approval": True},
                {"name": "Payment Dispatch", "requires_approval": False},
            ]
        }),
    },
    {
        "name": "New Vendor Onboarding",
        "description": "Compliance and legal checks for new supplier registration.",
        "version": 1,
        "is_active": True,
        "definition_json": json.dumps({
            "steps": [
                {"name": "Compliance Check", "requires_approval": False},
                {"name": "Legal Review", "requires_approval": True},
                {"name": "ERP Registration", "requires_approval": False},
            ]
        }),
    },
    {
        "name": "Data Retention Review",
        "description": "Annual review of data-retention policies against regulatory requirements.",
        "version": 1,
        "is_active": True,
        "definition_json": json.dumps({
            "steps": [
                {"name": "Data Catalogue Scan", "requires_approval": False},
                {"name": "Legal Compliance Review", "requires_approval": True},
                {"name": "Retention Policy Update", "requires_approval": True},
            ]
        }),
    },
]

# ---------------------------------------------------------------------------
# Demo documents and chunks
# ---------------------------------------------------------------------------

DEMO_DOCUMENTS: list[dict[str, Any]] = [
    {
        "filename": "data_retention_policy_v3.md",
        "original_filename": "data_retention_policy_v3.md",
        "doc_type": DocumentType.markdown.value,
        "status": DocumentStatus.indexed.value,
        "file_size_bytes": 4096,
        "description": "Corporate data-retention policy – version 3.",
        "chunks": [
            {
                "chunk_index": 0,
                "content": (
                    "LakEnterprises retains customer personal data for a maximum of 7 years "
                    "after the end of the contractual relationship, in accordance with GDPR "
                    "Article 5(1)(e) and applicable national law."
                ),
                "token_count": 42,
            },
            {
                "chunk_index": 1,
                "content": (
                    "Financial transaction records must be kept for a minimum of 10 years "
                    "as required by the EU Anti-Money-Laundering Directive (AMLD6)."
                ),
                "token_count": 36,
            },
            {
                "chunk_index": 2,
                "content": (
                    "All data subject access requests (DSARs) must be responded to within "
                    "30 calendar days of receipt. Extensions of up to 60 additional days "
                    "are permitted where the request is complex or numerous."
                ),
                "token_count": 45,
            },
        ],
    },
    {
        "filename": "gdpr_compliance_checklist.md",
        "original_filename": "gdpr_compliance_checklist.md",
        "doc_type": DocumentType.markdown.value,
        "status": DocumentStatus.indexed.value,
        "file_size_bytes": 2048,
        "description": "GDPR compliance checklist for new data processing activities.",
        "chunks": [
            {
                "chunk_index": 0,
                "content": (
                    "Before starting a new data processing activity, complete a Data "
                    "Protection Impact Assessment (DPIA) if the processing is likely to "
                    "result in a high risk to individuals' rights and freedoms."
                ),
                "token_count": 40,
            },
            {
                "chunk_index": 1,
                "content": (
                    "Maintain a Record of Processing Activities (RoPA) as required by "
                    "GDPR Article 30. The RoPA must include: purpose, data categories, "
                    "recipients, retention periods, and security measures."
                ),
                "token_count": 38,
            },
        ],
    },
    {
        "filename": "vendor_sla_standards.md",
        "original_filename": "vendor_sla_standards.md",
        "doc_type": DocumentType.markdown.value,
        "status": DocumentStatus.indexed.value,
        "file_size_bytes": 3200,
        "description": "SLA standards and KPIs required of all LakEnterprises vendors.",
        "chunks": [
            {
                "chunk_index": 0,
                "content": (
                    "All tier-1 vendors must achieve 99.9% uptime SLA for critical systems. "
                    "Tier-2 vendors must achieve 99.5% uptime. Measurement period is monthly "
                    "calendar month."
                ),
                "token_count": 36,
            },
            {
                "chunk_index": 1,
                "content": (
                    "Incident response SLAs: P1 (critical) – 1 hour initial response, "
                    "4 hour resolution target. P2 (high) – 4 hour response, 24 hour "
                    "resolution target. P3 (medium) – 1 business day response."
                ),
                "token_count": 44,
            },
        ],
    },
]

# ---------------------------------------------------------------------------
# Demo research session
# ---------------------------------------------------------------------------

DEMO_RESEARCH_QUESTION = (
    "What are LakEnterprises' data-retention obligations under GDPR and AMLD6, "
    "and which internal policy document governs the 7-year personal-data rule?"
)


# ---------------------------------------------------------------------------
# Seed functions
# ---------------------------------------------------------------------------


def seed_users(db: Session) -> dict[str, User]:
    """Insert demo users; return a name→User map."""
    users: dict[str, User] = {}
    for data in DEMO_USERS:
        user = _upsert_user(db, **data)
        users[user.role] = user
        logger.debug("Seeded user %s (%s)", user.email, user.role)
    return users


def seed_process_templates(db: Session, admin_user: User) -> list[ProcessTemplate]:
    """Insert demo process templates."""
    templates: list[ProcessTemplate] = []
    for data in DEMO_TEMPLATES:
        tmpl = _upsert_template(db, created_by_id=admin_user.id, **data)
        templates.append(tmpl)
        logger.debug("Seeded template: %s", tmpl.name)
    return templates


def seed_documents(db: Session, uploader: User) -> list[Document]:
    """Insert demo documents and their chunks."""
    docs: list[Document] = []
    for doc_data in DEMO_DOCUMENTS:
        chunks_data = doc_data.pop("chunks", [])
        doc = _upsert_document(db, uploader_id=uploader.id, **doc_data)
        doc.chunk_count = len(chunks_data)

        # Only add chunks if none exist yet
        from sqlalchemy import select
        existing_chunks = db.scalars(
            select(DocumentChunk).where(DocumentChunk.document_id == doc.id)
        ).all()
        if not existing_chunks:
            for chunk_data in chunks_data:
                chunk = DocumentChunk(document_id=doc.id, **chunk_data)
                db.add(chunk)
        docs.append(doc)
        logger.debug("Seeded document: %s (%d chunks)", doc.filename, len(chunks_data))
        # Restore chunks_data for idempotency
        doc_data["chunks"] = chunks_data
    db.flush()
    return docs


def seed_research_session(db: Session, analyst: User) -> ResearchSession:
    """Insert a completed demo research session."""
    from sqlalchemy import select

    # Check if session already exists
    stmt = select(ResearchSession).where(
        ResearchSession.question == DEMO_RESEARCH_QUESTION,
        ResearchSession.user_id == analyst.id,
    )
    existing = db.scalars(stmt).first()
    if existing:
        return existing

    session = ResearchSession(
        user_id=analyst.id,
        question=DEMO_RESEARCH_QUESTION,
        complexity=QueryComplexity.moderate.value,
        status=SessionStatus.completed.value,
        answer=(
            "LakEnterprises must retain customer personal data for 7 years after contract end "
            "(GDPR Art 5(1)(e)) and financial records for 10 years (AMLD6). "
            "These obligations are documented in `data_retention_policy_v3.md`."
        ),
        citations_json=json.dumps([
            "[data_retention_policy_v3.md – chunk #1]",
            "[data_retention_policy_v3.md – chunk #2]",
        ]),
        metadata_json=json.dumps({
            "strategies_used": ["vector"],
            "num_sub_questions": 1,
            "num_evidence": 2,
            "verification_ratio": 1.0,
        }),
        duration_ms=3200,
        started_at=_now(),
        completed_at=_now(),
    )
    db.add(session)
    db.flush()

    # Sub-question
    sq = ResearchSubQuestion(
        session_id=session.id,
        position=0,
        question=DEMO_RESEARCH_QUESTION,
        strategy=RetrievalStrategy.vector.value,
        answer="7 years for personal data; 10 years for financial records.",
        evidence_json=json.dumps([
            {
                "source": "data_retention_policy_v3.md",
                "text": "LakEnterprises retains customer personal data for a maximum of 7 years…",
                "verification_status": "verified",
            }
        ]),
        verified=True,
        verification_ratio="1.0",
    )
    db.add(sq)

    # Workflow events
    for etype, node in [
        (EventType.node_start.value, "analyze"),
        (EventType.node_end.value, "analyze"),
        (EventType.node_start.value, "retrieve"),
        (EventType.retrieval.value, "retrieve"),
        (EventType.node_end.value, "retrieve"),
        (EventType.node_start.value, "verify"),
        (EventType.node_end.value, "verify"),
        (EventType.node_start.value, "answer"),
        (EventType.node_end.value, "answer"),
    ]:
        ev = WorkflowEvent(
            session_id=session.id,
            event_type=etype,
            node_name=node,
            payload_json=json.dumps({}),
            duration_ms=200,
        )
        db.add(ev)

    db.flush()
    return session


def seed_audit_entries(db: Session, users: dict[str, User]) -> None:
    """Insert minimal audit entries for demo logins."""
    admin = users.get(UserRole.admin.value)
    analyst = users.get(UserRole.analyst.value)

    for user in [admin, analyst]:
        if user is None:
            continue
        entry = AuditLog(
            user_id=user.id,
            action=AuditAction.login.value,
            target_type="user",
            target_id=user.id,
            detail_json=json.dumps({"demo": True}),
        )
        db.add(entry)
    db.flush()


def seed_process_instance(
    db: Session, analyst: User, template: ProcessTemplate
) -> ProcessInstance:
    """Insert a demo process instance with tasks."""
    from sqlalchemy import select

    stmt = select(ProcessInstance).where(
        ProcessInstance.template_id == template.id,
        ProcessInstance.initiated_by_id == analyst.id,
    )
    existing = db.scalars(stmt).first()
    if existing:
        return existing

    instance = ProcessInstance(
        template_id=template.id,
        initiated_by_id=analyst.id,
        status=ProcessStatus.active.value,
        title="Q4 Vendor Invoice – TechCorp Solutions Ltd",
        context_json=json.dumps({"vendor": "TechCorp Solutions Ltd", "amount": 48500.00}),
    )
    db.add(instance)
    db.flush()

    definition = template.definition
    for i, step in enumerate(definition.get("steps", [])):
        task = ProcessTask(
            instance_id=instance.id,
            position=i,
            name=step["name"],
            description=f"Demo task: {step['name']}",
            status=TaskStatus.pending.value if i > 0 else TaskStatus.in_progress.value,
            requires_approval=step.get("requires_approval", False),
        )
        db.add(task)

    db.flush()
    return instance


# ---------------------------------------------------------------------------
# Main seed runner
# ---------------------------------------------------------------------------


def run_seed(db_url: str | None = None) -> None:
    """Run the full seed sequence.

    Args:
        db_url: Optional SQLAlchemy URL.  Defaults to ``settings.db_url``.
    """
    engine = make_engine(db_url) if db_url else None

    if engine:
        create_all_tables(engine)
        factory = make_session_factory(engine)
        db = factory()
        try:
            _do_seed(db)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    else:
        create_all_tables()
        with db_session() as db:
            _do_seed(db)
            db.commit()

    logger.info("Seed complete.")


def _do_seed(db: Session) -> None:
    """Execute all seed steps within an existing session."""
    logger.info("Seeding users …")
    users = seed_users(db)

    analyst = users[UserRole.analyst.value]
    admin = users[UserRole.admin.value]

    logger.info("Seeding process templates …")
    templates = seed_process_templates(db, admin)

    logger.info("Seeding documents …")
    seed_documents(db, uploader=analyst)

    logger.info("Seeding research session …")
    seed_research_session(db, analyst)

    logger.info("Seeding audit entries …")
    seed_audit_entries(db, users)

    if templates:
        logger.info("Seeding process instance …")
        seed_process_instance(db, analyst, templates[0])


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import logging as _logging

    _logging.basicConfig(level=_logging.INFO, format="%(levelname)s %(message)s")
    db_url_arg = sys.argv[1] if len(sys.argv) > 1 else None
    run_seed(db_url=db_url_arg)
    print("✅  Seed complete.")
