"""PII and secret scrubber for masking sensitive credentials and personal data."""

from __future__ import annotations

import re
from typing import Any, List, Pattern

from pydantic import BaseModel, Field


class DetectionItem(BaseModel):
    """Details of a detected sensitive string."""

    entity_type: str
    original_snippet: str
    replacement: str
    start_pos: int
    end_pos: int


class ScrubResult(BaseModel):
    """Result of scrubbing text for sensitive entities."""

    scrubbed_text: str
    detections: List[DetectionItem] = Field(default_factory=list)
    contains_pii: bool = False
    contains_secrets: bool = False

    @property
    def has_findings(self) -> bool:
        return self.contains_pii or self.contains_secrets

    @property
    def sanitized_text(self) -> str:
        return self.scrubbed_text


def _luhn_checksum(card_number_str: str) -> bool:
    """Verify Luhn algorithm checksum for credit card numbers."""
    digits = [int(c) for c in card_number_str if c.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    reverse_digits = digits[::-1]
    for idx, d in enumerate(reverse_digits):
        if idx % 2 == 1:
            doubled = d * 2
            checksum += doubled - 9 if doubled > 9 else doubled
        else:
            checksum += d
    return checksum % 10 == 0


class PIIScrubber:
    """Detects and redacts PII and secrets in text, prompts, and JSON payloads."""

    # ── Compiled Patterns ─────────────────────────────────────────────
    # Secrets
    AWS_KEY_PATTERN: Pattern = re.compile(r"\b(AKIA[0-9A-Z]{16})\b")
    OPENAI_KEY_PATTERN: Pattern = re.compile(r"\b(sk-[a-zA-Z0-9\-_]{20,})\b")
    JWT_PATTERN: Pattern = re.compile(
        r"\beyJ[A-Za-z0-9-_]+\.eyJ[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+\b"
    )
    PRIVATE_KEY_PATTERN: Pattern = re.compile(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"
    )
    CONN_STRING_PASS_PATTERN: Pattern = re.compile(
        r"((?:postgres|mysql|sqlite|redis|mongodb):\/\/[^:\s]+:)([^@\s]+)(@)"
    )
    GENERIC_SECRET_PATTERN: Pattern = re.compile(
        r"(?i)\b(api[_-]?key|secret|password|token)\s*[:=]\s*['\"]?([A-Za-z0-9_\-]{8,})['\"]?"
    )

    # PII
    SSN_PATTERN: Pattern = re.compile(r"\b(\d{3}-\d{2}-\d{4})\b")
    EMAIL_PATTERN: Pattern = re.compile(
        r"\b([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)\b"
    )
    PHONE_PATTERN: Pattern = re.compile(
        r"\b(?:\+?1[-. ]?)?\(?([0-9]{3})\)?[-. ]?([0-9]{3})[-. ]?([0-9]{4})\b"
    )
    CREDIT_CARD_CANDIDATE: Pattern = re.compile(
        r"\b(?:\d{4}[ -]?){3}\d{4}\b|\b\d{13,19}\b"
    )

    def __init__(self, mask_character: str = "*") -> None:
        self.mask_char = mask_character

    def scrub_text(self, text: str) -> ScrubResult:
        """Scrub all known secrets and PII from a single string."""
        if not text:
            return ScrubResult(scrubbed_text="")

        detections: List[DetectionItem] = []
        has_pii = False
        has_secrets = False
        result = text

        # 1. Private Keys
        for match in self.PRIVATE_KEY_PATTERN.finditer(result):
            snippet = match.group(0)
            replacement = "[REDACTED_PRIVATE_KEY]"
            detections.append(
                DetectionItem(
                    entity_type="PRIVATE_KEY",
                    original_snippet=snippet[:25] + "...",
                    replacement=replacement,
                    start_pos=match.start(),
                    end_pos=match.end(),
                )
            )
            has_secrets = True
        result = self.PRIVATE_KEY_PATTERN.sub("[REDACTED_PRIVATE_KEY]", result)

        # 2. Connection string passwords
        def _replace_conn_pass(m: re.Match) -> str:
            nonlocal has_secrets
            has_secrets = True
            detections.append(
                DetectionItem(
                    entity_type="DB_PASSWORD",
                    original_snippet=m.group(2)[:2] + "***",
                    replacement="[REDACTED_PASSWORD]",
                    start_pos=m.start(2),
                    end_pos=m.end(2),
                )
            )
            return f"{m.group(1)}[REDACTED_PASSWORD]{m.group(3)}"

        result = self.CONN_STRING_PASS_PATTERN.sub(_replace_conn_pass, result)

        # 3. AWS Access Keys
        for match in self.AWS_KEY_PATTERN.finditer(result):
            snippet = match.group(1)
            detections.append(
                DetectionItem(
                    entity_type="AWS_ACCESS_KEY",
                    original_snippet=snippet[:4] + "***",
                    replacement="[REDACTED_AWS_KEY]",
                    start_pos=match.start(),
                    end_pos=match.end(),
                )
            )
            has_secrets = True
        result = self.AWS_KEY_PATTERN.sub("[REDACTED_AWS_KEY]", result)

        # 4. OpenAI Keys
        for match in self.OPENAI_KEY_PATTERN.finditer(result):
            snippet = match.group(1)
            detections.append(
                DetectionItem(
                    entity_type="OPENAI_API_KEY",
                    original_snippet=snippet[:6] + "***",
                    replacement="[REDACTED_API_KEY]",
                    start_pos=match.start(),
                    end_pos=match.end(),
                )
            )
            has_secrets = True
        result = self.OPENAI_KEY_PATTERN.sub("[REDACTED_API_KEY]", result)

        # 5. JWT Tokens
        for match in self.JWT_PATTERN.finditer(result):
            snippet = match.group(0)
            detections.append(
                DetectionItem(
                    entity_type="JWT_TOKEN",
                    original_snippet=snippet[:10] + "...",
                    replacement="[REDACTED_JWT]",
                    start_pos=match.start(),
                    end_pos=match.end(),
                )
            )
            has_secrets = True
        result = self.JWT_PATTERN.sub("[REDACTED_JWT]", result)

        # 6. Generic Secrets (api_key="...", password="...")
        def _replace_generic_secret(m: re.Match) -> str:
            nonlocal has_secrets
            has_secrets = True
            key_name = m.group(1)
            secret_val = m.group(2)
            detections.append(
                DetectionItem(
                    entity_type="SECRET_CREDENTIAL",
                    original_snippet=secret_val[:2] + "***",
                    replacement="[REDACTED_SECRET]",
                    start_pos=m.start(2),
                    end_pos=m.end(2),
                )
            )
            return f"{key_name}=[REDACTED_SECRET]"

        result = self.GENERIC_SECRET_PATTERN.sub(_replace_generic_secret, result)

        # 7. Credit Cards (with Luhn check)
        for match in list(self.CREDIT_CARD_CANDIDATE.finditer(result)):
            raw_card = match.group(0)
            clean_digits = re.sub(r"\D", "", raw_card)
            if _luhn_checksum(clean_digits):
                detections.append(
                    DetectionItem(
                        entity_type="CREDIT_CARD",
                        original_snippet="****" + clean_digits[-4:],
                        replacement="[REDACTED_CREDIT_CARD]",
                        start_pos=match.start(),
                        end_pos=match.end(),
                    )
                )
                has_pii = True
                result = result.replace(raw_card, "[REDACTED_CREDIT_CARD]")

        # 8. SSN
        for match in self.SSN_PATTERN.finditer(result):
            snippet = match.group(1)
            detections.append(
                DetectionItem(
                    entity_type="SSN",
                    original_snippet="***-**-" + snippet[-4:],
                    replacement="[REDACTED_SSN]",
                    start_pos=match.start(),
                    end_pos=match.end(),
                )
            )
            has_pii = True
        result = self.SSN_PATTERN.sub("[REDACTED_SSN]", result)

        # 9. Email
        for match in self.EMAIL_PATTERN.finditer(result):
            snippet = match.group(1)
            parts = snippet.split("@")
            masked_name = parts[0][0] + "***" if len(parts[0]) > 1 else "***"
            detections.append(
                DetectionItem(
                    entity_type="EMAIL",
                    original_snippet=f"{masked_name}@{parts[1]}",
                    replacement="[REDACTED_EMAIL]",
                    start_pos=match.start(),
                    end_pos=match.end(),
                )
            )
            has_pii = True
        result = self.EMAIL_PATTERN.sub("[REDACTED_EMAIL]", result)

        # 10. Phone
        for match in self.PHONE_PATTERN.finditer(result):
            detections.append(
                DetectionItem(
                    entity_type="PHONE_NUMBER",
                    original_snippet="***-***-" + match.group(3),
                    replacement="[REDACTED_PHONE]",
                    start_pos=match.start(),
                    end_pos=match.end(),
                )
            )
            has_pii = True
        result = self.PHONE_PATTERN.sub("[REDACTED_PHONE]", result)

        return ScrubResult(
            scrubbed_text=result,
            detections=detections,
            contains_pii=has_pii,
            contains_secrets=has_secrets,
        )

    def scrub_dict(self, data: Any) -> Any:
        """Recursively scrub strings within nested dictionaries and lists."""
        if isinstance(data, str):
            return self.scrub_text(data).scrubbed_text
        elif isinstance(data, dict):
            return {k: self.scrub_dict(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self.scrub_dict(item) for item in data]
        return data


default_scrubber = PIIScrubber()
