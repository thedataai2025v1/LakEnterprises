"""Escalation and severity rules engine for automated incident and risk triage."""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from lakenterprises.services.audit import AuditService

logger = logging.getLogger(__name__)


class SeverityLevel(str, Enum):
    """Incident and risk severity tiers."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class EscalationDecision(BaseModel):
    """Result of evaluating escalation rules against an enterprise event."""

    severity: SeverityLevel = SeverityLevel.LOW
    should_escalate: bool = False
    requires_immediate_pager: bool = False
    target_role: str = "analyst"
    reasons: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    recommended_action: str = "Proceed with standard automated workflow."


class EscalationRulesEngine:
    """Deterministic rules engine categorizing risk and triggering human escalation."""

    def __init__(
        self,
        audit_service: Optional[AuditService] = None,
        critical_financial_threshold: float = 100000.0,
        high_financial_threshold: float = 10000.0,
    ) -> None:
        self.audit_service = audit_service or AuditService()
        self.critical_financial_threshold = critical_financial_threshold
        self.high_financial_threshold = high_financial_threshold

    def evaluate(
        self,
        event_type: str,
        payload: Dict[str, Any],
        user_id: str = "anonymous",
    ) -> EscalationDecision:
        """Evaluate deterministic rules across security, financial, and SLA factors."""
        reasons: List[str] = []
        tags: List[str] = [event_type.lower()]
        highest_severity = SeverityLevel.LOW
        requires_pager = False
        target_role = "analyst"
        action = "Proceed with standard automated workflow."

        # ── 1. Financial Impact Rules ─────────────────────────────────
        amount = float(payload.get("total_amount") or payload.get("amount") or 0.0)
        if amount >= self.critical_financial_threshold:
            highest_severity = SeverityLevel.CRITICAL
            reasons.append(
                f"Financial amount (${amount:,.2f}) exceeds critical "
                f"threshold (${self.critical_financial_threshold:,.2f})."
            )
            tags.append("financial_critical")
            requires_pager = True
            target_role = "admin"
            action = "Hold transaction and require dual-executive sign-off."
        elif amount >= self.high_financial_threshold:
            if highest_severity.value in ("LOW", "MEDIUM"):
                highest_severity = SeverityLevel.HIGH
            reasons.append(
                f"Financial amount (${amount:,.2f}) exceeds high threshold (${self.high_financial_threshold:,.2f})."
            )
            tags.append("financial_high")
            target_role = "manager"
            action = "Require manager approval before executing order."

        # ── 2. Security & Injection Rules ─────────────────────────────
        injection_score = float(payload.get("injection_score") or 0.0)
        has_injection = bool(payload.get("is_injected") or injection_score >= 0.5)
        if has_injection or injection_score >= 0.7:
            highest_severity = SeverityLevel.CRITICAL
            reasons.append(
                f"Severe prompt injection detected (score={injection_score}). Potential jailbreak attempt."
            )
            tags.append("security_injection_critical")
            requires_pager = True
            target_role = "admin"
            action = "Terminate session, quarantine input, and dispatch security incident alert."
        elif injection_score >= 0.4:
            if highest_severity.value in ("LOW", "MEDIUM"):
                highest_severity = SeverityLevel.HIGH
            reasons.append(
                f"Suspicious prompt pattern detected (score={injection_score})."
            )
            tags.append("security_suspicious")
            if target_role == "analyst":
                target_role = "manager"
            action = "Flag input for manual security review."

        # ── 3. PII & Privacy Rules ───────────────────────────────────
        if payload.get("contains_secrets") or payload.get("contains_pii"):
            findings_count = len(payload.get("detections") or [])
            if payload.get("contains_secrets"):
                if highest_severity.value in ("LOW", "MEDIUM"):
                    highest_severity = SeverityLevel.HIGH
                reasons.append("Plaintext credential or secret detected in payload.")
                tags.append("secret_leakage")
                target_role = "admin"
                action = "Redact credentials immediately and invalidate exposed tokens."
            elif findings_count > 3 or payload.get("has_ssn_or_card"):
                if highest_severity.value == "LOW":
                    highest_severity = SeverityLevel.MEDIUM
                reasons.append(
                    f"Multiple PII records detected ({findings_count} entities)."
                )
                tags.append("pii_sensitive")

        # ── 4. Customer SLA & Tier Rules ─────────────────────────────
        tier = str(payload.get("tier") or payload.get("customer_tier") or "").lower()
        if tier in ("vip", "platinum"):
            if payload.get("is_outage") or payload.get("ticket_priority") == "high":
                highest_severity = SeverityLevel.CRITICAL
                reasons.append(
                    f"Critical incident impacting {tier.upper()} SLA customer."
                )
                tags.append("sla_vip_breach")
                requires_pager = True
                target_role = "manager"
                action = "Dispatch incident response lead and notify account executive."
            else:
                if highest_severity.value == "LOW":
                    highest_severity = SeverityLevel.MEDIUM
                reasons.append(f"Action involves {tier.upper()} tier customer.")
                tags.append("sla_vip")

        should_escalate = highest_severity in (
            SeverityLevel.HIGH,
            SeverityLevel.CRITICAL,
        )

        decision = EscalationDecision(
            severity=highest_severity,
            should_escalate=should_escalate,
            requires_immediate_pager=requires_pager,
            target_role=target_role,
            reasons=reasons or ["Standard operational conditions met."],
            tags=list(set(tags)),
            recommended_action=action,
        )

        self._log_decision(event_type, user_id, decision)
        return decision

    def _log_decision(
        self, event_type: str, user_id: str, decision: EscalationDecision
    ) -> None:
        try:
            self.audit_service.log(
                action="ESCALATION_EVALUATION",
                user_id=user_id,
                details={
                    "event_type": event_type,
                    "severity": decision.severity.value,
                    "should_escalate": decision.should_escalate,
                    "requires_pager": decision.requires_immediate_pager,
                    "target_role": decision.target_role,
                    "reasons": decision.reasons,
                },
                severity="WARNING" if decision.should_escalate else "INFO",
            )
        except Exception as exc:
            logger.warning("Failed to record escalation audit entry: %s", exc)


default_rules_engine = EscalationRulesEngine()
