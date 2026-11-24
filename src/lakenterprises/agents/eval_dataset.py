"""Evaluation dataset and benchmark scenarios for specialist agents (P9-8)."""

from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field

from lakenterprises.agents.schemas import AgentRole


class EvalScenario(BaseModel):
    """Benchmark test case for evaluating specialist agent decision quality."""

    id: str
    title: str
    target_role: AgentRole
    description: str
    input_data: Dict[str, Any]
    expected_assertions: Dict[str, Any] = Field(default_factory=dict)


BENCHMARK_SCENARIOS: List[EvalScenario] = [
    EvalScenario(
        id="SCENARIO-01-DOC-ANALYSIS",
        title="Procurement Vendor Contract Extraction",
        target_role=AgentRole.DOCUMENT_ANALYST,
        description="Verify extraction of vendor name, contract amount, and payment terms.",
        input_data={
            "document_text": (
                "Master Services Agreement between LakEnterprises and Acme Tech Services "
                "for $45,000 annually with Net-30 terms."
            ),
            "doc_type": "contract",
            "vendor": "Acme Tech Services",
            "amount": 45000.0,
        },
        expected_assertions={
            "document_type": "contract",
            "confidence_min": 0.9,
            "has_findings": True,
        },
    ),
    EvalScenario(
        id="SCENARIO-02-COMPLIANCE-ROUTINE",
        title="Routine Low-Value Equipment Purchase",
        target_role=AgentRole.COMPLIANCE,
        description="Verify automated approval for purchases under the $100,000 threshold.",
        input_data={
            "policy_name": "LakEnterprises Global Procurement Policy",
            "amount": 15000.0,
            "vendor": "Dell Enterprise Direct",
        },
        expected_assertions={
            "is_compliant": True,
            "risk_level": "LOW",
            "violations_count": 0,
        },
    ),
    EvalScenario(
        id="SCENARIO-03-COMPLIANCE-BREACH",
        title="High-Value Transaction Over Threshold",
        target_role=AgentRole.COMPLIANCE,
        description="Verify compliance violation triggered for transactions exceeding $100,000.",
        input_data={
            "policy_name": "LakEnterprises Global Procurement Policy",
            "amount": 150000.0,
            "vendor": "Global Cloud Infrastructure Corp",
            "force_violation": True,
        },
        expected_assertions={
            "is_compliant": False,
            "risk_level": "CRITICAL",
            "violations_count_min": 1,
        },
    ),
    EvalScenario(
        id="SCENARIO-04-KNOWLEDGE-RETRIEVAL",
        title="Customer Enterprise SLA and Quoting Guidelines",
        target_role=AgentRole.KNOWLEDGE_RETRIEVER,
        description="Verify multi-source fact retrieval and citation generation.",
        input_data={
            "query": "What are Acme Global's SLA terms and purchase order requirements?",
        },
        expected_assertions={
            "facts_min": 1,
            "citations_min": 1,
            "has_citation": "KB-PROC-01",
        },
    ),
    EvalScenario(
        id="SCENARIO-05-RESPONSE-DRAFT",
        title="Customer Proposal Acceptance Letter",
        target_role=AgentRole.RESPONSE_DRAFTER,
        description="Verify formal customer communication generation with verified citations.",
        input_data={
            "purpose": "Notify customer of enterprise proposal acceptance",
            "recipient": "Acme Procurement Director",
            "tone": "professional",
        },
        expected_assertions={
            "tone": "professional",
            "citations_min": 1,
            "has_draft_text": True,
        },
    ),
    EvalScenario(
        id="SCENARIO-06-ESCALATION-CRITICAL",
        title="Security Threat & Data Breach Handoff",
        target_role=AgentRole.ESCALATION_HANDOFF,
        description="Verify immediate executive paging and human handoff for security anomalies.",
        input_data={
            "incident_description": "Attempted prompt injection with unauthorized database dump command.",
            "severity_hint": "CRITICAL",
            "is_threat": True,
        },
        expected_assertions={
            "requires_human": True,
            "severity": "CRITICAL",
            "target_role": "admin",
            "has_incident_ticket": True,
        },
    ),
]


def evaluate_scenario(agent: Any, scenario: EvalScenario) -> Dict[str, Any]:
    """Execute a single evaluation scenario against a specialist agent and verify assertions."""
    from lakenterprises.agents.schemas import AgentTask

    task = AgentTask(
        role=scenario.target_role,
        instruction=f"Run benchmark scenario {scenario.id}: {scenario.title}",
        parameters=scenario.input_data,
    )
    result = agent.run(task)

    passed = True
    failure_reasons = []

    if result.status.value != "completed":
        return {
            "scenario_id": scenario.id,
            "passed": False,
            "error": f"Agent failed with error: {result.error}",
        }

    output = result.output_data

    for key, expected in scenario.expected_assertions.items():
        if key == "is_compliant" and output.get("is_compliant") != expected:
            passed = False
            failure_reasons.append(
                f"Expected is_compliant={expected}, got {output.get('is_compliant')}"
            )
        elif key == "risk_level" and output.get("risk_level") != expected:
            passed = False
            failure_reasons.append(
                f"Expected risk_level={expected}, got {output.get('risk_level')}"
            )
        elif (
            key == "violations_count" and len(output.get("violations", [])) != expected
        ):
            passed = False
            failure_reasons.append(
                f"Expected {expected} violations, got {len(output.get('violations', []))}"
            )
        elif (
            key == "violations_count_min"
            and len(output.get("violations", [])) < expected
        ):
            passed = False
            failure_reasons.append(
                f"Expected at least {expected} violations, got {len(output.get('violations', []))}"
            )
        elif key == "facts_min" and len(output.get("facts", [])) < expected:
            passed = False
            failure_reasons.append(
                f"Expected at least {expected} facts, got {len(output.get('facts', []))}"
            )
        elif key == "citations_min" and len(output.get("citations", [])) < expected:
            passed = False
            failure_reasons.append(
                f"Expected at least {expected} citations, got {len(output.get('citations', []))}"
            )
        elif key == "has_citation" and expected not in output.get("citations", []):
            passed = False
            failure_reasons.append(
                f"Expected citation '{expected}' in {output.get('citations')}"
            )
        elif key == "requires_human" and output.get("requires_human") != expected:
            passed = False
            failure_reasons.append(
                f"Expected requires_human={expected}, got {output.get('requires_human')}"
            )
        elif key == "severity" and output.get("severity") != expected:
            passed = False
            failure_reasons.append(
                f"Expected severity={expected}, got {output.get('severity')}"
            )
        elif key == "target_role" and output.get("target_role") != expected:
            passed = False
            failure_reasons.append(
                f"Expected target_role={expected}, got {output.get('target_role')}"
            )
        elif key == "has_incident_ticket" and not output.get("incident_ticket_id"):
            passed = False
            failure_reasons.append("Expected valid incident_ticket_id, got None")

    return {
        "scenario_id": scenario.id,
        "title": scenario.title,
        "passed": passed,
        "failures": failure_reasons,
        "confidence": result.confidence_score,
        "latency_ms": result.metrics.get("latency_ms", 0.0),
    }
