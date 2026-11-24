"""Policy engine for role-based access control and approval gating on agent tools."""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from pydantic import BaseModel

from lakenterprises.models.enums import ApprovalStatus
from lakenterprises.services.approval import ApprovalService
from lakenterprises.services.audit import AuditService
from lakenterprises.tools.base import RiskLevel, ToolCategory
from lakenterprises.tools.registry import ToolRegistry, default_registry

logger = logging.getLogger(__name__)


class PolicyDecision(BaseModel):
    """Result of policy evaluation for tool invocation."""

    allowed: bool
    reason: str
    requires_approval: bool = False
    approval_status: Optional[str] = None


class ToolPolicyEngine:
    """Enforces enterprise security policies, RBAC, and approval gates for tool executions."""

    def __init__(
        self,
        registry: Optional[ToolRegistry] = None,
        approval_service: Optional[ApprovalService] = None,
        audit_service: Optional[AuditService] = None,
    ) -> None:
        self.registry = registry or default_registry
        self.approval_service = approval_service or ApprovalService()
        self.audit_service = audit_service or AuditService()

    def evaluate(
        self,
        tool_name: str,
        user_roles: List[str],
        user_id: str = "anonymous",
        approval_id: Optional[str] = None,
        parameters: Optional[dict[str, Any]] = None,
    ) -> PolicyDecision:
        """Evaluate if the user with given roles is permitted to invoke the tool."""
        tool = self.registry.get(tool_name)
        if not tool:
            decision = PolicyDecision(
                allowed=False,
                reason=f"Tool '{tool_name}' is not registered.",
            )
            self._log_decision(tool_name, user_id, decision)
            return decision

        # Normalize roles
        roles = [r.lower() for r in user_roles]
        if not roles:
            roles = ["viewer"]

        # 1. Allowed roles on the tool definition
        tool_allowed_roles = [r.lower() for r in tool.allowed_roles]
        if not any(r in tool_allowed_roles for r in roles):
            decision = PolicyDecision(
                allowed=False,
                reason=f"Roles {roles} are not authorized for tool '{tool_name}'. Allowed: {tool.allowed_roles}",
            )
            self._log_decision(tool_name, user_id, decision)
            return decision

        # 2. Role-tier capability restrictions
        is_admin = "admin" in roles
        is_manager = "manager" in roles
        is_analyst = "analyst" in roles
        is_viewer = not (is_admin or is_manager or is_analyst)

        # Viewer restriction: read-only & low-risk only
        if is_viewer:
            if tool.category != ToolCategory.READ or tool.risk_level != RiskLevel.LOW:
                decision = PolicyDecision(
                    allowed=False,
                    reason="Viewer role is restricted to low-risk read-only tools.",
                )
                self._log_decision(tool_name, user_id, decision)
                return decision

        # Analyst restriction: cannot run critical actions without approval
        if is_analyst and not (is_manager or is_admin):
            if tool.risk_level == RiskLevel.CRITICAL:
                decision = PolicyDecision(
                    allowed=False,
                    requires_approval=True,
                    reason="Critical risk tools cannot be directly executed by analysts.",
                )
                self._log_decision(tool_name, user_id, decision)
                return decision

        # 3. Approval gating check
        needs_approval = tool.requires_approval
        # High/critical write tools require approval unless executed by admin or approval decision by manager
        if (
            tool.category in (ToolCategory.WRITE, ToolCategory.ACTION)
            and tool.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
            and not (is_admin or (is_manager and tool.name == "approval_decision"))
        ):
            needs_approval = True

        if needs_approval:
            if not approval_id:
                decision = PolicyDecision(
                    allowed=False,
                    requires_approval=True,
                    reason=f"Tool '{tool_name}' requires manager or admin approval before execution.",
                )
                self._log_decision(tool_name, user_id, decision)
                return decision

            # Validate approval request in approval service
            appr = self.approval_service.get_request(approval_id)
            if not appr:
                decision = PolicyDecision(
                    allowed=False,
                    requires_approval=True,
                    reason=f"Approval request '{approval_id}' was not found.",
                )
                self._log_decision(tool_name, user_id, decision)
                return decision

            appr_status = (
                getattr(appr, "status", None)
                if hasattr(appr, "status")
                else appr.get("status")
            )
            appr_comment = (
                getattr(appr, "comment", None)
                if hasattr(appr, "comment")
                else (appr.get("comment") if isinstance(appr, dict) else None)
            )

            if appr_status == ApprovalStatus.APPROVED.value:
                decision = PolicyDecision(
                    allowed=True,
                    requires_approval=True,
                    approval_status=appr_status,
                    reason=f"Approved under request '{approval_id}'.",
                )
                self._log_decision(tool_name, user_id, decision)
                return decision
            elif appr_status == ApprovalStatus.REJECTED.value:
                decision = PolicyDecision(
                    allowed=False,
                    requires_approval=True,
                    approval_status=appr_status,
                    reason=f"Approval request '{approval_id}' was rejected: {appr_comment}",
                )
                self._log_decision(tool_name, user_id, decision)
                return decision
            else:
                decision = PolicyDecision(
                    allowed=False,
                    requires_approval=True,
                    approval_status=appr_status,
                    reason=f"Approval request '{approval_id}' is still pending review.",
                )
                self._log_decision(tool_name, user_id, decision)
                return decision

        decision = PolicyDecision(
            allowed=True,
            reason="Policy check passed.",
        )
        self._log_decision(tool_name, user_id, decision)
        return decision

    def _log_decision(
        self, tool_name: str, user_id: str, decision: PolicyDecision
    ) -> None:
        try:
            self.audit_service.log(
                action="TOOL_POLICY_CHECK",
                user_id=user_id,
                details={
                    "tool": tool_name,
                    "allowed": decision.allowed,
                    "reason": decision.reason,
                    "requires_approval": decision.requires_approval,
                    "approval_status": decision.approval_status,
                },
                severity="INFO" if decision.allowed else "WARNING",
            )
        except Exception as exc:
            logger.warning("Failed to record audit log for policy check: %s", exc)
