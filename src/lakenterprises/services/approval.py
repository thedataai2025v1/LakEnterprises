"""Approval governance service for human-in-the-loop sign-offs."""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from lakenterprises.models.entities import ApprovalRequest
from lakenterprises.models.enums import ApprovalStatus
from lakenterprises.repositories import ApprovalRequestRepository

logger = logging.getLogger(__name__)


class ApprovalService:
    """Service managing human review gates and audit decisions."""

    def __init__(self, db: Optional[Session] = None) -> None:
        if db is None:
            from lakenterprises.db import get_db_session

            db = get_db_session()
        self.db = db
        self.approval_repo = ApprovalRequestRepository(db)

    def request_approval(
        self,
        target_type: str,
        target_id: str,
        action: str,
        requested_by_id: str,
    ) -> ApprovalRequest:
        """Create a new pending approval gate."""
        req = self.approval_repo.create(
            target_type=target_type,
            target_id=target_id,
            action=action,
            requested_by_id=requested_by_id,
            status=ApprovalStatus.PENDING.value,
        )
        self.db.commit()
        return req

    def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        return self.approval_repo.get_by_id(request_id)

    def list_requests(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ApprovalRequest]:
        return self.approval_repo.get_all(status=status, limit=limit, offset=offset)

    def list_pending(self, limit: int = 50, offset: int = 0) -> list[ApprovalRequest]:
        return self.approval_repo.get_pending(limit=limit, offset=offset)

    def approve(
        self,
        request_id: str,
        reviewed_by_id: str,
        comment: Optional[str] = None,
    ) -> ApprovalRequest:
        """Approve a pending request."""
        req = self.approval_repo.get_by_id(request_id)
        if not req:
            raise ValueError(f"Approval request '{request_id}' not found")
        if req.status != ApprovalStatus.PENDING.value:
            raise ValueError(f"Approval request is already '{req.status}'")

        updated = self.approval_repo.update_decision(
            request_id,
            status=ApprovalStatus.APPROVED.value,
            reviewed_by_id=reviewed_by_id,
            comment=comment,
        )
        self.db.commit()
        return updated  # type: ignore[return-value]

    def reject(
        self,
        request_id: str,
        reviewed_by_id: str,
        comment: Optional[str] = None,
    ) -> ApprovalRequest:
        """Reject a pending request."""
        req = self.approval_repo.get_by_id(request_id)
        if not req:
            raise ValueError(f"Approval request '{request_id}' not found")
        if req.status != ApprovalStatus.PENDING.value:
            raise ValueError(f"Approval request is already '{req.status}'")

        updated = self.approval_repo.update_decision(
            request_id,
            status=ApprovalStatus.REJECTED.value,
            reviewed_by_id=reviewed_by_id,
            comment=comment,
        )
        self.db.commit()
        return updated  # type: ignore[return-value]
