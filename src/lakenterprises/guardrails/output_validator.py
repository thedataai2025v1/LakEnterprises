"""Output schema validation, JSON repair, citation grounding, and leakage checks."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple, Type

from pydantic import BaseModel, Field

from lakenterprises.guardrails.pii_scrubber import (PIIScrubber,
                                                    default_scrubber)

logger = logging.getLogger(__name__)


class ValidationResult(BaseModel):
    """Result of agent response validation."""

    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    repaired_output: Optional[Any] = None
    citations_valid: bool = True
    found_citations: List[str] = Field(default_factory=list)
    invalid_citations: List[str] = Field(default_factory=list)
    contains_leakage: bool = False


class OutputSchemaValidator:
    """Validates structured model outputs, enforces schemas, and validates citations."""

    CITATION_PATTERN = re.compile(r"\[(\d+|[a-zA-Z0-9_\-:]+)\]")

    def __init__(
        self,
        scrubber: Optional[PIIScrubber] = None,
        max_length_chars: int = 50000,
        min_length_chars: int = 1,
    ) -> None:
        self.scrubber = scrubber or default_scrubber
        self.max_length_chars = max_length_chars
        self.min_length_chars = min_length_chars

    def repair_json_string(self, text: str) -> Optional[Dict[str, Any]]:
        """Attempt to extract and parse valid JSON from LLM generation."""
        if not text:
            return None

        cleaned = text.strip()

        # 1. Strip markdown fences: ```json ... ```
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
        if fence_match:
            cleaned = fence_match.group(1).strip()

        # 2. Try direct parse
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # 3. Simple regex repairs: fix trailing commas before } or ]
        repaired = re.sub(r",\s*([\]}])", r"\1", cleaned)
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            pass

        return None

    def validate_schema(
        self,
        output: Any,
        expected_model: Optional[Type[BaseModel]] = None,
        expected_keys: Optional[List[str]] = None,
    ) -> Tuple[bool, List[str], Optional[Any]]:
        """Validate whether output matches expected Pydantic model or dictionary keys."""
        errors: List[str] = []
        parsed = output

        # If string, attempt JSON repair
        if isinstance(output, str):
            parsed = self.repair_json_string(output)
            if parsed is None and (expected_model or expected_keys):
                errors.append("Output string could not be parsed as valid JSON.")
                return False, errors, None

        # Check required dictionary keys
        if expected_keys and isinstance(parsed, dict):
            for k in expected_keys:
                if k not in parsed:
                    errors.append(f"Missing required key '{k}' in output payload.")

        # Validate with Pydantic model
        if expected_model and parsed is not None:
            try:
                if isinstance(parsed, dict):
                    validated_obj = expected_model(**parsed)
                    parsed = validated_obj.model_dump()
                elif isinstance(parsed, expected_model):
                    parsed = parsed.model_dump()
                else:
                    errors.append(
                        f"Expected instance of {expected_model.__name__}, got {type(parsed).__name__}."
                    )
            except Exception as exc:
                errors.append(f"Schema validation error: {str(exc)}")

        return len(errors) == 0, errors, parsed

    def validate_citations(
        self,
        text: str,
        valid_evidence_ids: List[str],
    ) -> Tuple[bool, List[str], List[str]]:
        """Check that every citation marker in text resolves to a valid evidence identifier."""
        if not text:
            return True, [], []

        raw_matches = self.CITATION_PATTERN.findall(text)
        found = list(dict.fromkeys(raw_matches))  # deduplicate preserving order
        invalid: List[str] = []

        valid_set = set(str(e) for e in valid_evidence_ids)

        for cite in found:
            if cite not in valid_set:
                invalid.append(cite)

        return len(invalid) == 0, found, invalid

    def check_output_leakage(self, text: str) -> Tuple[bool, List[str]]:
        """Verify that agent output does not leak plaintext private keys or sensitive credentials."""
        res = self.scrubber.scrub_text(text)
        leakage_errors: List[str] = []
        if res.contains_secrets:
            types = [d.entity_type for d in res.detections]
            leakage_errors.append(
                f"Agent response contains raw credentials or secrets: {types}"
            )
        return res.contains_secrets, leakage_errors

    def validate(
        self,
        output_text: str,
        expected_model: Optional[Type[BaseModel]] = None,
        expected_keys: Optional[List[str]] = None,
        valid_evidence_ids: Optional[List[str]] = None,
    ) -> ValidationResult:
        """Run complete output validation: length, schema, leakage, and citations."""
        errors: List[str] = []

        # 1. Length checks
        length = len(output_text) if output_text else 0
        if length < self.min_length_chars:
            errors.append(
                f"Output length ({length}) is below minimum threshold ({self.min_length_chars})."
            )
        if length > self.max_length_chars:
            errors.append(
                f"Output length ({length}) exceeds maximum threshold ({self.max_length_chars})."
            )

        # 2. Secret leakage check
        contains_leakage, leak_errors = self.check_output_leakage(output_text)
        errors.extend(leak_errors)

        # 3. Schema validation
        schema_valid, schema_errors, repaired_data = self.validate_schema(
            output=output_text,
            expected_model=expected_model,
            expected_keys=expected_keys,
        )
        errors.extend(schema_errors)

        # 4. Citation verification
        citations_valid = True
        found_cites: List[str] = []
        invalid_cites: List[str] = []
        if valid_evidence_ids is not None:
            citations_valid, found_cites, invalid_cites = self.validate_citations(
                text=output_text,
                valid_evidence_ids=valid_evidence_ids,
            )
            if not citations_valid:
                errors.append(
                    f"Invalid or hallucinated citations found: {invalid_cites}"
                )

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            repaired_output=repaired_data,
            citations_valid=citations_valid,
            found_citations=found_cites,
            invalid_citations=invalid_cites,
            contains_leakage=contains_leakage,
        )


default_output_validator = OutputSchemaValidator()
