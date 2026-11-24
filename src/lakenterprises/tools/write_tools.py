"""Approval-gated write and action tools mutating enterprise state."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from lakenterprises.integrations.base import (CRMAdapter, EmailAdapter,
                                              ERPAdapter)
from lakenterprises.integrations.mock_crm import MockCRMAdapter
from lakenterprises.integrations.mock_email import MockEmailAdapter
from lakenterprises.integrations.mock_erp import MockERPAdapter
from lakenterprises.services.approval import ApprovalService
from lakenterprises.services.process import ProcessService
from lakenterprises.tools.base import BaseTool, RiskLevel, ToolCategory


class CRMUpdateTicketTool(BaseTool):
    """Updates status or appends notes to a customer support ticket."""

    name = "crm_update_ticket"
    description = "Update customer support ticket status and append engineer notes."
    category = ToolCategory.WRITE
    risk_level = RiskLevel.MEDIUM
    requires_approval = False
    allowed_roles = ["analyst", "manager", "admin"]

    def __init__(self, crm_adapter: Optional[CRMAdapter] = None) -> None:
        self.crm_adapter = crm_adapter or MockCRMAdapter()

    def run(
        self,
        ticket_id: str,
        status: Optional[str] = None,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not ticket_id:
            raise ValueError("ticket_id is required.")
        return self.crm_adapter.update_ticket(
            ticket_id=ticket_id, status=status, note=note
        )

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "ticket_id": {
                    "type": "string",
                    "description": "Identifier of the ticket to update (e.g. TCK-501).",
                },
                "status": {
                    "type": "string",
                    "description": "New status for the ticket ('open', 'in_progress', 'resolved').",
                },
                "note": {
                    "type": "string",
                    "description": "Work note or resolution description to append.",
                },
            },
            "required": ["ticket_id"],
        }


class ERPCreatePurchaseOrderTool(BaseTool):
    """Creates a formal purchase order in the ERP system. Requires manager approval."""

    name = "erp_create_purchase_order"
    description = "Create a formal enterprise purchase order in the ERP system. High-value mutation."
    category = ToolCategory.WRITE
    risk_level = RiskLevel.HIGH
    requires_approval = True
    allowed_roles = ["analyst", "manager", "admin"]

    def __init__(self, erp_adapter: Optional[ERPAdapter] = None) -> None:
        self.erp_adapter = erp_adapter or MockERPAdapter()

    def run(
        self,
        vendor_id: str,
        items: List[Dict[str, Any]],
        total_amount: float,
    ) -> Dict[str, Any]:
        if not vendor_id:
            raise ValueError("vendor_id is required.")
        if not items:
            raise ValueError("items list cannot be empty.")
        if total_amount <= 0:
            raise ValueError("total_amount must be greater than zero.")
        return self.erp_adapter.create_purchase_order(
            vendor_id=vendor_id, items=items, total_amount=total_amount
        )

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "vendor_id": {
                    "type": "string",
                    "description": "Vendor identifier (e.g. VND-ACME).",
                },
                "items": {
                    "type": "array",
                    "description": "List of purchase order line items with sku, name, qty, price.",
                    "items": {"type": "object"},
                },
                "total_amount": {
                    "type": "number",
                    "description": "Total order amount in USD.",
                },
            },
            "required": ["vendor_id", "items", "total_amount"],
        }


class EmailDispatchTool(BaseTool):
    """Sends transactional email, incident alerts, or status communications."""

    name = "email_dispatch"
    description = "Send official alert, status notification or resolution email to customer or team."
    category = ToolCategory.ACTION
    risk_level = RiskLevel.MEDIUM
    requires_approval = False
    allowed_roles = ["analyst", "manager", "admin"]

    def __init__(self, email_adapter: Optional[EmailAdapter] = None) -> None:
        self.email_adapter = email_adapter or MockEmailAdapter()

    def run(
        self,
        recipient: str,
        subject: str,
        body: str,
        cc: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        if not recipient:
            raise ValueError("recipient is required.")
        if not subject or not subject.strip():
            raise ValueError("subject cannot be empty.")
        if not body or not body.strip():
            raise ValueError("body cannot be empty.")
        return self.email_adapter.send_email(
            to=recipient, subject=subject, body=body, cc=cc
        )

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "recipient": {
                    "type": "string",
                    "description": "Target email address.",
                },
                "subject": {
                    "type": "string",
                    "description": "Email subject header.",
                },
                "body": {
                    "type": "string",
                    "description": "Email body content in plain text or markdown.",
                },
                "cc": {
                    "type": "array",
                    "description": "Optional list of CC email addresses.",
                    "items": {"type": "string"},
                },
            },
            "required": ["recipient", "subject", "body"],
        }


class ProcessTaskSubmitTool(BaseTool):
    """Updates and marks a process workflow task as completed."""

    name = "process_task_submit"
    description = "Submit completed work output for an assigned process task and advance its state."
    category = ToolCategory.WRITE
    risk_level = RiskLevel.LOW
    requires_approval = False
    allowed_roles = ["analyst", "manager", "admin"]

    def __init__(self, process_service: Optional[ProcessService] = None) -> None:
        self.process_service = process_service or ProcessService()

    def run(
        self,
        task_id: str,
        status: str = "completed",
        output: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not task_id:
            raise ValueError("task_id is required.")
        updated = self.process_service.update_task(
            task_id=task_id, status=status, output=output
        )
        return {
            "task_id": getattr(updated, "id", task_id),
            "status": getattr(updated, "status", status),
            "output": getattr(updated, "output", output),
        }

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "Task identifier to update.",
                },
                "status": {
                    "type": "string",
                    "description": "New task status ('completed', 'failed', 'in_progress').",
                    "default": "completed",
                },
                "output": {
                    "type": "object",
                    "description": "Structured findings or result payload.",
                },
            },
            "required": ["task_id"],
        }


class ApprovalDecisionTool(BaseTool):
    """Human-in-the-loop decision tool for approving or rejecting gated actions."""

    name = "approval_decision"
    description = "Approve or reject a pending human-in-the-loop approval request with audit comments."
    category = ToolCategory.ACTION
    risk_level = RiskLevel.HIGH
    requires_approval = False
    allowed_roles = ["manager", "admin"]

    def __init__(self, approval_service: Optional[ApprovalService] = None) -> None:
        self.approval_service = approval_service or ApprovalService()

    def run(
        self,
        approval_id: str,
        decision: str,
        reviewer_id: str,
        comments: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not approval_id:
            raise ValueError("approval_id is required.")
        decision_clean = decision.strip().lower()
        if decision_clean == "approve":
            appr = self.approval_service.approve(
                request_id=approval_id,
                reviewed_by_id=reviewer_id,
                comment=comments or "Approved via agent tool.",
            )
        elif decision_clean == "reject":
            appr = self.approval_service.reject(
                request_id=approval_id,
                reviewed_by_id=reviewer_id,
                comment=comments or "Rejected via agent tool.",
            )
        else:
            raise ValueError(
                f"Invalid decision '{decision}'. Must be 'approve' or 'reject'."
            )

        return {
            "request_id": getattr(appr, "id", approval_id),
            "status": getattr(appr, "status", decision_clean),
            "reviewed_by_id": getattr(appr, "reviewed_by_id", reviewer_id),
            "comment": getattr(appr, "comment", comments),
        }

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "approval_id": {
                    "type": "string",
                    "description": "Identifier of the pending approval request.",
                },
                "decision": {
                    "type": "string",
                    "description": "Decision: 'approve' or 'reject'.",
                },
                "reviewer_id": {
                    "type": "string",
                    "description": "User ID of the reviewing manager/admin.",
                },
                "comments": {
                    "type": "string",
                    "description": "Explanatory review notes.",
                },
            },
            "required": ["approval_id", "decision", "reviewer_id"],
        }
