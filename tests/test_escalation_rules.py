"""Unit tests for Escalation and Severity Rules Engine."""

from lakenterprises.guardrails.escalation_rules import (EscalationRulesEngine,
                                                        SeverityLevel)
from lakenterprises.services.audit import AuditService


class TestEscalationRulesEngine:
    def test_standard_operational_low_severity(self):
        engine = EscalationRulesEngine()
        dec = engine.evaluate(
            event_type="PROCESS_START",
            payload={"amount": 500.0, "tier": "growth"},
        )
        assert dec.severity == SeverityLevel.LOW
        assert dec.should_escalate is False
        assert dec.requires_immediate_pager is False
        assert dec.target_role == "analyst"

    def test_high_financial_threshold_escalation(self):
        engine = EscalationRulesEngine()
        dec = engine.evaluate(
            event_type="PURCHASE_ORDER",
            payload={"amount": 25000.0},
        )
        assert dec.severity == SeverityLevel.HIGH
        assert dec.should_escalate is True
        assert dec.target_role == "manager"
        assert any("financial amount" in r.lower() for r in dec.reasons)

    def test_critical_financial_threshold_escalation(self):
        engine = EscalationRulesEngine()
        dec = engine.evaluate(
            event_type="PURCHASE_ORDER",
            payload={"amount": 150000.0},
        )
        assert dec.severity == SeverityLevel.CRITICAL
        assert dec.should_escalate is True
        assert dec.requires_immediate_pager is True
        assert dec.target_role == "admin"

    def test_prompt_injection_security_escalation(self):
        engine = EscalationRulesEngine()
        dec = engine.evaluate(
            event_type="PROMPT_CHECK",
            payload={"injection_score": 0.85, "is_injected": True},
        )
        assert dec.severity == SeverityLevel.CRITICAL
        assert dec.should_escalate is True
        assert dec.requires_immediate_pager is True
        assert "security_injection_critical" in dec.tags

    def test_vip_customer_outage_escalation(self):
        engine = EscalationRulesEngine()
        dec = engine.evaluate(
            event_type="CUSTOMER_INCIDENT",
            payload={"tier": "platinum", "is_outage": True},
        )
        assert dec.severity == SeverityLevel.CRITICAL
        assert dec.should_escalate is True
        assert dec.requires_immediate_pager is True
        assert dec.target_role == "manager"

    def test_audit_service_logging(self):
        audit = AuditService(db_session=None)
        engine = EscalationRulesEngine(audit_service=audit)
        dec = engine.evaluate(
            event_type="ORDER_MUTATION",
            payload={"amount": 50000.0},
            user_id="analyst_test",
        )
        assert dec.should_escalate is True
        logs = audit.get_logs(action="ESCALATION_EVALUATION")
        assert len(logs) >= 1
        entry = logs[0]
        assert entry["details"]["severity"] == "HIGH"
        assert entry["details"]["should_escalate"] is True
