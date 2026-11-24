"""Unit tests for agent schemas and FakeLLMHarness (P9-1)."""

from lakenterprises.agents.fake_llm import FakeLLMHarness
from lakenterprises.agents.schemas import (
    AgentResult,
    AgentRole,
    AgentTask,
    AgentTaskStatus,
)


def test_agent_schemas_validation():
    task = AgentTask(
        role=AgentRole.DOCUMENT_ANALYST,
        instruction="Analyze contract terms.",
        context={"doc_id": "DOC-101"},
    )
    assert task.task_id is not None
    assert task.role == AgentRole.DOCUMENT_ANALYST

    result = AgentResult(
        task_id=task.task_id,
        role=AgentRole.DOCUMENT_ANALYST,
        status=AgentTaskStatus.COMPLETED,
        output_data={"key_findings": ["Valid terms."]},
        citations=["DOC-101"],
    )
    assert result.status == AgentTaskStatus.COMPLETED
    assert result.confidence_score == 1.0


def test_fake_llm_harness_default_roles():
    harness = FakeLLMHarness()

    # Supervisor
    sup_out = harness.generate(AgentRole.SUPERVISOR, "Plan procurement workflow")
    assert sup_out["next_agent"] == "document_analyst"
    assert len(sup_out["subtasks"]) >= 3

    # Document Analyst
    doc_out = harness.generate(AgentRole.DOCUMENT_ANALYST, "Analyze contract")
    assert "vendor" in doc_out["extracted_entities"]
    assert doc_out["confidence"] >= 0.9

    # Compliance
    comp_out = harness.generate(
        AgentRole.COMPLIANCE, "Check compliance", context={"amount": 15000.0}
    )
    assert comp_out["is_compliant"] is True
    assert comp_out["risk_level"] == "LOW"

    # Escalation
    esc_out = harness.generate(
        AgentRole.ESCALATION_HANDOFF, "Check threat", context={"is_threat": True}
    )
    assert esc_out["requires_human"] is True
    assert esc_out["severity"] == "CRITICAL"


def test_fake_llm_custom_registration():
    harness = FakeLLMHarness()
    custom_reply = {"custom_verdict": "AUTHORIZED_BY_TEST"}
    harness.register_response("special_trigger_phrase", custom_reply)

    out = harness.generate(
        AgentRole.SUPERVISOR, "This contains special_trigger_phrase in prompt"
    )
    assert out["custom_verdict"] == "AUTHORIZED_BY_TEST"
    assert len(harness.call_history) == 1
