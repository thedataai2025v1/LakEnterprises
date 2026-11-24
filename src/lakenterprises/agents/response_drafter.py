"""Response Drafting Agent (P9-6)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from lakenterprises.agents.base import BaseSpecialistAgent
from lakenterprises.agents.schemas import AgentRole, AgentTask, ResponseDraftResult


class ResponseDraftingAgent(BaseSpecialistAgent[ResponseDraftResult]):
    """Specialist agent drafting structured, grounded enterprise communications and memos."""

    role = AgentRole.RESPONSE_DRAFTER
    output_schema = ResponseDraftResult

    def draft_response(
        self,
        purpose: str,
        facts: Optional[List[str]] = None,
        recipient: str = "customer",
        tone: str = "professional",
        context: Optional[Dict[str, Any]] = None,
    ) -> ResponseDraftResult:
        """Draft a formal communication grounded in verified evidence."""
        task = AgentTask(
            role=self.role,
            instruction=f"Draft response for purpose: {purpose}",
            context=context or {},
            parameters={
                "purpose": purpose,
                "facts": facts or [],
                "recipient": recipient,
                "tone": tone,
            },
        )
        result = self.run(task)
        if result.status.value == "completed":
            return ResponseDraftResult.model_validate(result.output_data)
        return ResponseDraftResult(
            draft_text="Draft generation failed.",
            recipient=recipient,
            tone=tone,
        )
