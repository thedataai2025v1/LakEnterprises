"""Unit tests for Phase 11 escalation routing and SLA timer management (P11-3)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from lakenterprises.workflow.escalation import EscalationRouter, EscalationTier


def test_evaluate_tier_routine_analyst() -> None:
    tier, target_role, sla_hours, reason = EscalationRouter.evaluate_tier(
        amount=2500.0,
        risk_level="LOW",
        has_violations=False,
    )
    assert tier == EscalationTier.TIER_1_ANALYST
    assert target_role == "analyst"
    assert sla_hours == 24.0
    assert "routine" in reason.lower() or "analyst" in reason.lower()


def test_evaluate_tier_manager() -> None:
    tier, target_role, sla_hours, reason = EscalationRouter.evaluate_tier(
        amount=25000.0,
        risk_level="MEDIUM",
        has_violations=False,
    )
    assert tier == EscalationTier.TIER_2_MANAGER
    assert target_role == "manager"
    assert sla_hours == 8.0


def test_evaluate_tier_director_compliance_breach() -> None:
    tier, target_role, sla_hours, reason = EscalationRouter.evaluate_tier(
        amount=65000.0,
        risk_level="HIGH",
        has_violations=True,
    )
    assert tier == EscalationTier.TIER_3_DIRECTOR
    assert target_role == "director"
    assert sla_hours == 4.0


def test_evaluate_tier_executive_over_threshold() -> None:
    tier, target_role, sla_hours, reason = EscalationRouter.evaluate_tier(
        amount=150000.0,
        risk_level="CRITICAL",
        has_violations=True,
    )
    assert tier == EscalationTier.TIER_4_EXECUTIVE
    assert target_role == "admin"
    assert sla_hours == 1.0
    assert "100k" in reason or "Executive" in reason


def test_calculate_sla_active() -> None:
    now = datetime.now(timezone.utc)
    sla_info = EscalationRouter.calculate_sla(
        tier=EscalationTier.TIER_2_MANAGER,
        created_at=now,
        now=now,
    )
    assert sla_info.tier == EscalationTier.TIER_2_MANAGER
    assert sla_info.sla_hours == 8.0
    assert sla_info.is_breached is False
    assert sla_info.remaining_seconds > 0.0
    assert sla_info.elapsed_seconds == 0.0


def test_calculate_sla_breached() -> None:
    now = datetime.now(timezone.utc)
    created_at = now - timedelta(hours=3)  # 3 hours elapsed for 1h SLA

    sla_info = EscalationRouter.calculate_sla(
        tier=EscalationTier.TIER_4_EXECUTIVE,
        created_at=created_at,
        sla_hours_override=1.0,
        now=now,
    )
    assert sla_info.tier == EscalationTier.TIER_4_EXECUTIVE
    assert sla_info.is_breached is True
    assert sla_info.remaining_seconds == 0.0
    assert sla_info.elapsed_seconds >= 10800.0
