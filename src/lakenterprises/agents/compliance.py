"""Compliance Check Agent (P9-4)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from lakenterprises.agents.base import BaseSpecialistAgent
from lakenterprises.agents.schemas import AgentRole, AgentTask, ComplianceResult


class ComplianceAgent(BaseSpecialistAgent[ComplianceResult]):
    """Specialist agent checking transactions, vendor agreements, and processes against policies."""

    role = AgentRole.COMPLIANCE
    output_schema = ComplianceResult

    def check_compliance(
        self,
        policy_name: str,
        transaction_details: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> ComplianceResult:
        """Evaluate a proposed action or transaction against enterprise compliance rules."""
        task = AgentTask(
            role=self.role,
            instruction=f"Audit transaction against policy '{policy_name}'",
            context=context or {},
            parameters={
                "policy_name": policy_name,
                "amount": transaction_details.get("amount", 0.0),
                "vendor": transaction_details.get("vendor"),
                **transaction_details,
            },
        )
        result = self.run(task)
        if result.status.value == "completed":
            return ComplianceResult.model_validate(result.output_data)
        return ComplianceResult(
            is_compliant=False,
            policy_name=policy_name,
            recommendation="Compliance evaluation failed.",
            risk_level="HIGH",
        )
