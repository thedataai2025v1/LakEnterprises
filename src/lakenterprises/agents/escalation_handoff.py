"""Escalation and Handoff Agent (P9-7)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from lakenterprises.agents.base import BaseSpecialistAgent
from lakenterprises.agents.schemas import AgentRole, AgentTask, EscalationHandoffResult


class EscalationHandoffAgent(BaseSpecialistAgent[EscalationHandoffResult]):
    """Specialist agent evaluating operational threats and formatting human handoff packets."""

    role = AgentRole.ESCALATION_HANDOFF
    output_schema = EscalationHandoffResult

    def evaluate_escalation(
        self,
        incident_description: str,
        severity_hint: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> EscalationHandoffResult:
        """Analyze an incident and determine whether to page on-call personnel or halt processing."""
        task = AgentTask(
            role=self.role,
            instruction=f"Evaluate escalation requirement for: {incident_description}",
            context=context or {},
            parameters={
                "incident_description": incident_description,
                "severity": severity_hint or "LOW",
                "is_threat": (severity_hint in ("HIGH", "CRITICAL")),
            },
        )
        result = self.run(task)
        if result.status.value == "completed":
            return EscalationHandoffResult.model_validate(result.output_data)
        return EscalationHandoffResult(
            requires_human=True,
            severity="HIGH",
            target_role="manager",
            escalation_reason="Escalation analysis failed; failing closed to human manager.",
        )
