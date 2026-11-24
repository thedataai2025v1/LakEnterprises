"""Unit tests for Escalation and Handoff Agent (P9-7)."""

from lakenterprises.agents.escalation_handoff import EscalationHandoffAgent
from lakenterprises.agents.schemas import EscalationHandoffResult


def test_escalation_agent_routine():
    agent = EscalationHandoffAgent()
    res = agent.evaluate_escalation(
        incident_description="User asked routine documentation question",
        severity_hint="LOW",
    )

    assert isinstance(res, EscalationHandoffResult)
    assert res.requires_human is False
    assert res.severity == "LOW"
    assert res.target_role == "analyst"


def test_escalation_agent_threat_handoff():
    agent = EscalationHandoffAgent()
    res = agent.evaluate_escalation(
        incident_description="Repeated SQL injection probe detected on auth endpoint",
        severity_hint="CRITICAL",
    )

    assert isinstance(res, EscalationHandoffResult)
    assert res.requires_human is True
    assert res.severity == "CRITICAL"
    assert res.target_role == "admin"
    assert res.incident_ticket_id == "INC-7701"
    assert "Page on-call" in res.recommended_actions[0]
