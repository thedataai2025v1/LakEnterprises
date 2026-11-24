"""FastAPI routes for Guardrails and Security operations."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from lakenterprises.auth.middleware import get_current_user
from lakenterprises.guardrails.escalation_rules import (EscalationDecision,
                                                        default_rules_engine)
from lakenterprises.guardrails.injection_guard import (InjectionCheckResult,
                                                       default_injection_guard)
from lakenterprises.guardrails.output_validator import (
    ValidationResult, default_output_validator)
from lakenterprises.guardrails.pii_scrubber import (ScrubResult,
                                                    default_scrubber)

router = APIRouter(prefix="/api/v1/guardrails", tags=["guardrails"])


class ScrubRequest(BaseModel):
    text: str = Field(..., description="Text to scan and redact")


class InjectionCheckRequest(BaseModel):
    text: str = Field(..., description="Prompt or query to evaluate for injection")
    strict: bool = Field(
        False, description="Raise security error if injection detected"
    )


class OutputValidationRequest(BaseModel):
    output_text: str = Field(
        ..., description="Agent or model response text to validate"
    )
    valid_evidence_ids: Optional[List[str]] = Field(
        None, description="Allowed citation IDs"
    )
    expected_keys: Optional[List[str]] = Field(
        None, description="Required JSON dictionary keys"
    )


class EscalationRequest(BaseModel):
    event_type: str = Field(..., description="Type of enterprise event")
    payload: Dict[str, Any] = Field(
        default_factory=dict, description="Event metadata and metrics"
    )


@router.post("/scrub", response_model=ScrubResult)
def scrub_pii(
    req: ScrubRequest,
    _user: Dict[str, Any] = Depends(get_current_user),
) -> ScrubResult:
    """Scan and redact PII and secret credentials in text."""
    return default_scrubber.scrub_text(req.text)


@router.post("/check-injection", response_model=InjectionCheckResult)
def check_prompt_injection(
    req: InjectionCheckRequest,
    _user: Dict[str, Any] = Depends(get_current_user),
) -> InjectionCheckResult:
    """Evaluate text for jailbreaks, prompt injection, and delimiter spoofing."""
    return default_injection_guard.check(req.text, strict=req.strict)


@router.post("/validate-output", response_model=ValidationResult)
def validate_output(
    req: OutputValidationRequest,
    _user: Dict[str, Any] = Depends(get_current_user),
) -> ValidationResult:
    """Validate model output against schema, citations, and credential leakage."""
    return default_output_validator.validate(
        output_text=req.output_text,
        valid_evidence_ids=req.valid_evidence_ids,
        expected_keys=req.expected_keys,
    )


@router.post("/evaluate-escalation", response_model=EscalationDecision)
def evaluate_escalation(
    req: EscalationRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> EscalationDecision:
    """Run deterministic rules to classify severity and determine if human paging is required."""
    user_id = current_user.get("user_id", "anonymous")
    return default_rules_engine.evaluate(
        event_type=req.event_type,
        payload=req.payload,
        user_id=user_id,
    )
