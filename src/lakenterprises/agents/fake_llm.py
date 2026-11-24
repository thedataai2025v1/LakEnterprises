"""Offline deterministic LLM harness for testing and executing specialist agents."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional

from lakenterprises.agents.schemas import AgentRole

logger = logging.getLogger(__name__)


class FakeLLMHarness:
    """Deterministic LLM test harness providing schema-valid specialist responses."""

    def __init__(
        self,
        custom_responses: Optional[Dict[str, Any]] = None,
        simulate_latency: float = 0.0,
        error_rate: float = 0.0,
    ) -> None:
        self.custom_responses: Dict[str, Any] = custom_responses or {}
        self.simulate_latency = simulate_latency
        self.error_rate = error_rate
        self.call_history: List[Dict[str, Any]] = []

    def register_response(self, key: str, response: Any) -> None:
        """Register a specific mock response for a key or prompt fragment."""
        self.custom_responses[key] = response

    def generate(
        self,
        role: AgentRole,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate a deterministic response tailored to the requested agent role."""
        if self.simulate_latency > 0:
            time.sleep(self.simulate_latency)

        start_time = time.perf_counter()

        # Check for registered custom mock response
        for k, v in self.custom_responses.items():
            if k.lower() in prompt.lower():
                self.call_history.append(
                    {"role": role, "prompt": prompt, "response": v, "matched_key": k}
                )
                return v if isinstance(v, dict) else json.loads(v)

        ctx = context or {}

        # Default role-based mock responses
        if role == AgentRole.SUPERVISOR:
            output = {
                "goal": ctx.get("goal") or prompt[:80],
                "next_agent": "document_analyst",
                "planned_agents": [
                    "document_analyst",
                    "compliance",
                    "response_drafter",
                ],
                "subtasks": [
                    {
                        "step": 1,
                        "agent": "document_analyst",
                        "task": "Extract contract terms",
                    },
                    {
                        "step": 2,
                        "agent": "compliance",
                        "task": "Check liability limits",
                    },
                    {
                        "step": 3,
                        "agent": "response_drafter",
                        "task": "Draft approval memo",
                    },
                ],
                "is_complete": False,
                "final_summary": None,
            }

        elif role == AgentRole.DOCUMENT_ANALYST:
            output = {
                "document_id": ctx.get("document_id") or "DOC-404",
                "document_type": ctx.get("doc_type") or "procurement_contract",
                "key_findings": [
                    "Vendor proposes Net-30 payment terms.",
                    "Annual commitment value is $45,000.",
                    "Warranty clause capped at 90 days.",
                ],
                "extracted_entities": {
                    "vendor": ctx.get("vendor") or "Acme Tech Services",
                    "amount": ctx.get("amount") or 45000.0,
                    "effective_date": "2026-04-01",
                },
                "risk_signals": (
                    ["Missing limitation of liability clause."]
                    if ctx.get("high_risk")
                    else []
                ),
                "confidence": 0.95,
            }

        elif role == AgentRole.COMPLIANCE:
            amount = float(ctx.get("amount") or 0.0)
            is_compliant = amount < 100000.0 and not ctx.get("force_violation")
            violations = []
            if not is_compliant:
                violations.append(
                    {
                        "rule_id": "POL-FIN-100K",
                        "rule_name": "Executive Sign-Off Threshold",
                        "description": (
                            f"Transaction amount (${amount:,.2f}) exceeds "
                            "single-approver threshold ($100,000)."
                        ),
                        "severity": "CRITICAL" if amount >= 100000.0 else "HIGH",
                        "clause_reference": "Corp Procurement Handbook Section 4.2",
                    }
                )
            output = {
                "is_compliant": is_compliant,
                "policy_name": "LakEnterprises Global Procurement & Risk Policy",
                "violations": violations,
                "recommendation": (
                    "Proceed with automated execution."
                    if is_compliant
                    else "Halt automated action. Route to Executive Board."
                ),
                "risk_level": "CRITICAL" if not is_compliant else "LOW",
            }

        elif role == AgentRole.KNOWLEDGE_RETRIEVER:
            output = {
                "query": prompt[:60],
                "facts": [
                    {
                        "source": "knowledge_base",
                        "locator": "policies/procurement_v3.md",
                        "snippet": "All hardware purchases above $10k require 3 vendor quotes.",
                        "relevance_score": 0.92,
                        "citation_id": "KB-PROC-01",
                    },
                    {
                        "source": "crm",
                        "locator": "accounts/CUST-1001",
                        "snippet": "Acme Global operates on Gold enterprise SLA with Net-30 invoicing.",
                        "relevance_score": 0.88,
                        "citation_id": "CRM-ACME-02",
                    },
                ],
                "citations": ["KB-PROC-01", "CRM-ACME-02"],
                "coverage_assessment": "complete",
            }

        elif role == AgentRole.RESPONSE_DRAFTER:
            output = {
                "draft_text": (
                    "Dear Partner,\n\nWe have reviewed your enterprise proposal and confirmed compliance "
                    "with our security and financial guidelines [KB-PROC-01]. We are pleased to proceed.\n\n"
                    "Best regards,\nLakEnterprises Operations"
                ),
                "recipient": ctx.get("recipient") or "customer",
                "tone": "professional",
                "citations": ["KB-PROC-01"],
                "key_points": [
                    "Proposal reviewed",
                    "Compliance confirmed",
                    "Execution in progress",
                ],
                "actions_proposed": [
                    "Execute purchase order",
                    "Send confirmation email",
                ],
            }

        elif role == AgentRole.ESCALATION_HANDOFF:
            severity = ctx.get("severity") or (
                "CRITICAL" if ctx.get("is_threat") else "LOW"
            )
            requires_human = severity in ("HIGH", "CRITICAL")
            output = {
                "requires_human": requires_human,
                "severity": severity,
                "target_role": (
                    "admin"
                    if severity == "CRITICAL"
                    else ("manager" if severity == "HIGH" else "analyst")
                ),
                "escalation_reason": (
                    f"Operational event classified as {severity} risk requiring supervisor authorization."
                    if requires_human
                    else "Routine event within automated processing tolerances."
                ),
                "recommended_actions": (
                    ["Page on-call incident response team", "Freeze affected account"]
                    if requires_human
                    else ["Continue automated workflow"]
                ),
                "incident_ticket_id": "INC-7701" if requires_human else None,
            }

        else:
            output = {"raw_response": f"Processed {role.value} prompt successfully."}

        latency_ms = (time.perf_counter() - start_time) * 1000.0
        self.call_history.append(
            {
                "role": role,
                "prompt": prompt,
                "response": output,
                "latency_ms": latency_ms,
            }
        )
        return output


default_fake_llm = FakeLLMHarness()
