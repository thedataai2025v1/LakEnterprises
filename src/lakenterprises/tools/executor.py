"""Executor coordinating tool lookup, policy enforcement, approval gates, and execution."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from lakenterprises.services.approval import ApprovalService
from lakenterprises.services.audit import AuditService
from lakenterprises.tools.base import ToolResult
from lakenterprises.tools.policy import ToolPolicyEngine
from lakenterprises.tools.registry import ToolRegistry, default_registry

logger = logging.getLogger(__name__)


class ToolExecutor:
    """Safe execution coordinator for agent tools with policy gating and audit logging."""

    def __init__(
        self,
        registry: Optional[ToolRegistry] = None,
        policy_engine: Optional[ToolPolicyEngine] = None,
        approval_service: Optional[ApprovalService] = None,
        audit_service: Optional[AuditService] = None,
    ) -> None:
        self.registry = registry or default_registry
        self.approval_service = approval_service or ApprovalService()
        self.audit_service = audit_service or AuditService()
        self.policy_engine = policy_engine or ToolPolicyEngine(
            registry=self.registry,
            approval_service=self.approval_service,
            audit_service=self.audit_service,
        )

    def execute(
        self,
        tool_name: str,
        parameters: Optional[Dict[str, Any]] = None,
        user_roles: Optional[List[str]] = None,
        user_id: str = "anonymous",
        approval_id: Optional[str] = None,
    ) -> ToolResult:
        """Execute tool safely with full policy evaluation, approval checks, and telemetry."""
        params = parameters or {}
        roles = user_roles or ["analyst"]
        start_time = time.perf_counter()

        # 1. Policy evaluation
        decision = self.policy_engine.evaluate(
            tool_name=tool_name,
            user_roles=roles,
            user_id=user_id,
            approval_id=approval_id,
            parameters=params,
        )

        if not decision.allowed:
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            # If rejected because approval is needed and none was provided, create a pending request
            created_approval_id = approval_id
            if decision.requires_approval and not approval_id:
                try:
                    appr = self.approval_service.request_approval(
                        target_type="tool",
                        target_id=tool_name,
                        action="execute_tool",
                        requested_by_id=user_id,
                    )
                    created_approval_id = (
                        getattr(appr, "id", None)
                        if hasattr(appr, "id")
                        else appr.get("request_id")
                    )
                except Exception as exc:
                    logger.warning("Failed to auto-create approval request: %s", exc)

            return ToolResult(
                success=False,
                error=decision.reason,
                execution_time_ms=elapsed_ms,
                requires_approval=decision.requires_approval,
                approval_request_id=created_approval_id,
                metadata={"reason": decision.reason},
            )

        # 2. Retrieve tool
        tool = self.registry.get(tool_name)
        if not tool:
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return ToolResult(
                success=False,
                error=f"Tool '{tool_name}' was not found in registry.",
                execution_time_ms=elapsed_ms,
            )

        # 3. Execution
        try:
            output = tool.run(**params)
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

            self.audit_service.log(
                action="TOOL_EXECUTION",
                user_id=user_id,
                details={
                    "tool": tool_name,
                    "parameters": params,
                    "duration_ms": elapsed_ms,
                    "approval_id": approval_id,
                },
                severity="INFO",
            )

            return ToolResult(
                success=True,
                output=output,
                execution_time_ms=elapsed_ms,
                requires_approval=decision.requires_approval,
                approval_request_id=approval_id,
                metadata={"approval_status": decision.approval_status},
            )
        except Exception as exc:
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.error("Error executing tool '%s': %s", tool_name, exc, exc_info=True)

            self.audit_service.log(
                action="TOOL_EXECUTION_ERROR",
                user_id=user_id,
                details={
                    "tool": tool_name,
                    "parameters": params,
                    "duration_ms": elapsed_ms,
                    "error": str(exc),
                },
                severity="ERROR",
            )

            return ToolResult(
                success=False,
                error=str(exc),
                execution_time_ms=elapsed_ms,
                requires_approval=decision.requires_approval,
                approval_request_id=approval_id,
            )
