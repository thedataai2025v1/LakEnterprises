"""Unit and integration tests for ApprovalService."""

import pytest

from lakenterprises.db import get_db_session, reset_db
from lakenterprises.models.enums import ApprovalStatus
from lakenterprises.services.approval import ApprovalService


@pytest.fixture(autouse=True)
def setup_database():
    reset_db()
    yield
    reset_db()


def test_approval_lifecycle():
    with get_db_session() as session:
        service = ApprovalService(session)

        # 1. Request approval
        req = service.request_approval(
            target_type="process_instance",
            target_id="proc-inst-123",
            action="deploy_to_production",
            requested_by_id="user-analyst-1",
        )
        assert req.id is not None
        assert req.status == ApprovalStatus.PENDING.value
        assert req.action == "deploy_to_production"

        # 2. List pending
        pending = service.list_pending()
        assert len(pending) == 1
        assert pending[0].id == req.id

        # 3. Approve
        approved = service.approve(
            req.id,
            reviewed_by_id="user-manager-1",
            comment="Changes reviewed and verified against policy.",
        )
        assert approved.status == ApprovalStatus.APPROVED.value
        assert approved.reviewed_by_id == "user-manager-1"
        assert approved.comment == "Changes reviewed and verified against policy."

        # 4. Verify cannot approve or reject twice
        with pytest.raises(ValueError, match="already"):
            service.approve(req.id, reviewed_by_id="user-manager-2")

        with pytest.raises(ValueError, match="already"):
            service.reject(req.id, reviewed_by_id="user-manager-2")


def test_approval_rejection():
    with get_db_session() as session:
        service = ApprovalService(session)

        req = service.request_approval(
            target_type="document_deletion",
            target_id="doc-456",
            action="delete",
            requested_by_id="user-analyst-1",
        )

        rejected = service.reject(
            req.id,
            reviewed_by_id="user-admin-1",
            comment="Deletion rejected: document is under retention hold.",
        )
        assert rejected.status == ApprovalStatus.REJECTED.value
        assert rejected.reviewed_by_id == "user-admin-1"
        assert "retention hold" in rejected.comment


def test_approval_not_found():
    with get_db_session() as session:
        service = ApprovalService(session)
        with pytest.raises(ValueError, match="not found"):
            service.approve("non-existent-id", reviewed_by_id="admin")
