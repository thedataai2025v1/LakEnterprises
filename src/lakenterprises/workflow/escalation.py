"""Escalation routing matrix and SLA timer management (P11-3)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class EscalationTier(str, Enum):
    """Multi-tier governance escalation levels."""

    TIER_1_ANALYST = "tier_1_analyst"
    TIER_2_MANAGER = "tier_2_manager"
    TIER_3_DIRECTOR = "tier_3_director"
    TIER_4_EXECUTIVE = "tier_4_executive"


@dataclass
class SLAStatus:
    """SLA timer status and deadline telemetry."""

    tier: EscalationTier
    target_role: str
    sla_hours: float
    created_at: str
    deadline: str
    elapsed_seconds: float
    remaining_seconds: float
    is_breached: bool
    escalation_reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tier": self.tier.value,
            "target_role": self.target_role,
            "sla_hours": self.sla_hours,
            "created_at": self.created_at,
            "deadline": self.deadline,
            "elapsed_seconds": round(self.elapsed_seconds, 1),
            "remaining_seconds": round(self.remaining_seconds, 1),
            "is_breached": self.is_breached,
            "escalation_reason": self.escalation_reason,
        }


class EscalationRouter:
    """Determines escalation tiers, assigned roles, and SLA deadlines based on transaction risk."""

    # Default policy matrix: (Tier, target_role, SLA in hours)
    ROUTING_MATRIX: Dict[EscalationTier, Tuple[str, float]] = {
        EscalationTier.TIER_1_ANALYST: ("analyst", 24.0),
        EscalationTier.TIER_2_MANAGER: ("manager", 8.0),
        EscalationTier.TIER_3_DIRECTOR: ("director", 4.0),
        EscalationTier.TIER_4_EXECUTIVE: ("admin", 1.0),
    }

    @classmethod
    def evaluate_tier(
        cls,
        amount: float = 0.0,
        risk_level: str = "LOW",
        has_violations: bool = False,
        severity_hint: Optional[str] = None,
    ) -> Tuple[EscalationTier, str, float, str]:
        """Classify operational incident into appropriate escalation tier, target role, SLA, and reason."""
        norm_severity = (severity_hint or risk_level).upper()

        if amount >= 100000.0 or norm_severity == "CRITICAL":
            tier = EscalationTier.TIER_4_EXECUTIVE
            reason = (
                f"Critical risk or high transaction value (${amount:,.2f} >= $100k) "
                "requires Executive / CFO sign-off."
            )
        elif amount >= 50000.0 or norm_severity == "HIGH" or has_violations:
            tier = EscalationTier.TIER_3_DIRECTOR
            reason = (
                f"High financial value (${amount:,.2f}) or compliance breach "
                "requires Director authorization."
            )
        elif amount >= 10000.0 or norm_severity == "MEDIUM":
            tier = EscalationTier.TIER_2_MANAGER
            reason = f"Transaction amount (${amount:,.2f}) requires Operational Manager review."
        else:
            tier = EscalationTier.TIER_1_ANALYST
            reason = (
                "Standard transaction within routine analyst processing thresholds."
            )

        target_role, sla_hours = cls.ROUTING_MATRIX[tier]
        return tier, target_role, sla_hours, reason

    @classmethod
    def calculate_sla(
        cls,
        tier: EscalationTier,
        created_at: Optional[datetime | str] = None,
        sla_hours_override: Optional[float] = None,
        now: Optional[datetime] = None,
        reason: str = "",
    ) -> SLAStatus:
        """Calculate SLA metrics, deadline, elapsed time, and breach condition."""
        current_time = now or _now_utc()

        if created_at is None:
            start_dt = current_time
        elif isinstance(created_at, str):
            try:
                start_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except Exception:
                start_dt = current_time
        else:
            start_dt = created_at

        target_role, default_sla = cls.ROUTING_MATRIX.get(tier, ("analyst", 24.0))
        sla_hours = (
            sla_hours_override if sla_hours_override is not None else default_sla
        )
        deadline_dt = start_dt + timedelta(hours=sla_hours)

        elapsed_sec = max(0.0, (current_time - start_dt).total_seconds())
        remaining_sec = (deadline_dt - current_time).total_seconds()
        is_breached = remaining_sec <= 0.0

        return SLAStatus(
            tier=tier,
            target_role=target_role,
            sla_hours=sla_hours,
            created_at=start_dt.isoformat(),
            deadline=deadline_dt.isoformat(),
            elapsed_seconds=elapsed_sec,
            remaining_seconds=max(0.0, remaining_sec),
            is_breached=is_breached,
            escalation_reason=reason
            or f"Escalated to {target_role} with {sla_hours}h SLA.",
        )
