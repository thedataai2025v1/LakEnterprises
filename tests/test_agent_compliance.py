"""Unit tests for Compliance Check Agent (P9-4)."""

from lakenterprises.agents.compliance import ComplianceAgent
from lakenterprises.agents.schemas import ComplianceResult


def test_compliance_agent_routine_transaction():
    agent = ComplianceAgent()
    res = agent.check_compliance(
        policy_name="LakEnterprises Procurement Policy",
        transaction_details={"amount": 12000.0, "vendor": "Dell Direct"},
    )

    assert isinstance(res, ComplianceResult)
    assert res.is_compliant is True
    assert res.risk_level == "LOW"
    assert len(res.violations) == 0
    assert "Proceed" in res.recommendation


def test_compliance_agent_over_threshold_violation():
    agent = ComplianceAgent()
    res = agent.check_compliance(
        policy_name="LakEnterprises Procurement Policy",
        transaction_details={"amount": 180000.0, "vendor": "Megacorp Systems"},
    )

    assert isinstance(res, ComplianceResult)
    assert res.is_compliant is False
    assert res.risk_level == "CRITICAL"
    assert len(res.violations) >= 1
    assert res.violations[0].rule_id == "POL-FIN-100K"
    assert "Executive Board" in res.recommendation
