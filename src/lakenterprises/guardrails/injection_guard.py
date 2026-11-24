"""Prompt injection detection, score assessment, and input wrapping guard."""

from __future__ import annotations

import base64
import logging
import re
from typing import List, Pattern, Tuple

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SecurityViolationError(ValueError):
    """Raised when strict prompt injection or security boundary violation is detected."""

    pass


class InjectionCheckResult(BaseModel):
    """Assessment returned after inspecting input for prompt injection."""

    is_injected: bool
    risk_score: float = Field(ge=0.0, le=1.0)
    risk_level: str  # "SAFE", "SUSPICIOUS", "HIGH", "CRITICAL"
    matched_patterns: List[str] = Field(default_factory=list)
    sanitized_text: str


class PromptInjectionGuard:
    """Multi-vector prompt injection detection engine."""

    # High severity patterns (Direct jailbreak / instruction override)
    HIGH_SEVERITY_PATTERNS: List[Tuple[str, Pattern]] = [
        (
            "OVERRIDE_INSTRUCTIONS",
            re.compile(
                r"(?i)\b(?:ignore|disregard|forget|bypass)\s+(?:all\s+)?"
                r"(?:previous|prior|above|existing|system)\s+(?:instructions|prompts|directives|rules|constraints)\b"
            ),
        ),
        (
            "ROLEPLAY_JAILBREAK",
            re.compile(
                r"(?i)\b(?:you\s+are\s+now|act\s+as|pretend\s+to\s+be)\s+(?:an?\s+)?"
                r"(?:dan|unfiltered|jailbroken|evil|unrestricted|god\s+mode)\b"
            ),
        ),
        (
            "SYSTEM_PROMPT_LEAK",
            re.compile(
                r"(?i)\b(?:print|repeat|output|reveal|show|display|echo)\s+(?:your\s+)?"
                r"(?:entire\s+)?(?:initial|original|secret|system)?\s*(?:system\s+)?"
                r"(?:prompt|instructions|rules|pre-prompt)\b"
            ),
        ),
        (
            "DIRECTIVE_SPOOFING",
            re.compile(
                r"(?i)\b(?:new\s+system\s+(?:instruction|directive)|developer\s+mode\s+enabled|sudo\s+mode\s+on)\b"
            ),
        ),
    ]

    # Delimiter and special token hijacking
    DELIMITER_PATTERNS: List[Tuple[str, Pattern]] = [
        ("SYSTEM_TAG_OPEN", re.compile(r"<\s*system\s*>", re.IGNORECASE)),
        ("SYSTEM_TAG_CLOSE", re.compile(r"<\s*/\s*system\s*>", re.IGNORECASE)),
        ("LLAMA_INST_TAG", re.compile(r"\[/?INST\]", re.IGNORECASE)),
        ("CHATML_TAG", re.compile(r"<\|im_(?:start|end)\|>", re.IGNORECASE)),
        ("SYS_DELIMITER", re.compile(r"<<SYS>>|<</SYS>>", re.IGNORECASE)),
        (
            "PROMPT_BORDER_SPOOF",
            re.compile(
                r"---+(?:START|BEGIN)\s+(?:SYSTEM|ADMIN)\s+PROMPT---+", re.IGNORECASE
            ),
        ),
    ]

    # Suspicious phrases (moderate risk, contextual)
    SUSPICIOUS_PATTERNS: List[Tuple[str, Pattern]] = [
        (
            "HYPOTHETICAL_OVERRIDE",
            re.compile(
                r"(?i)\b(?:in\s+a\s+hypothetical\s+world|hypothetically\s+speaking)\s*,\s*"
                r"(?:if\s+there\s+were\s+no\s+rules|you\s+had\s+no\s+limits)\b"
            ),
        ),
        (
            "REVERSE_PSYCHOLOGY",
            re.compile(r"(?i)\bdo\s+not\s+follow\s+any\s+safety\s+guidelines\b"),
        ),
        (
            "BASE64_INSTRUCTION_PREFIX",
            re.compile(r"(?i)\b(?:base64|b64)\s+(?:decode|instruction)\s*[:=]\b"),
        ),
    ]

    def __init__(self, threshold: float = 0.5) -> None:
        self.threshold = threshold

    def check(self, text: str, strict: bool = False) -> InjectionCheckResult:
        """Inspect text for prompt injection indicators and return assessment."""
        if not text or not text.strip():
            return InjectionCheckResult(
                is_injected=False,
                risk_score=0.0,
                risk_level="SAFE",
                matched_patterns=[],
                sanitized_text=text or "",
            )

        matched: List[str] = []
        score = 0.0

        # 1. High severity checks (weight: 0.7 each)
        for name, pattern in self.HIGH_SEVERITY_PATTERNS:
            if pattern.search(text):
                matched.append(name)
                score += 0.7

        # 2. Delimiter hijacking checks (weight: 0.5 each)
        for name, pattern in self.DELIMITER_PATTERNS:
            if pattern.search(text):
                matched.append(name)
                score += 0.5

        # 3. Suspicious pattern checks (weight: 0.3 each)
        for name, pattern in self.SUSPICIOUS_PATTERNS:
            if pattern.search(text):
                matched.append(name)
                score += 0.3

        # 4. Check for embedded base64 blocks that decode into injections
        b64_matches = re.findall(r"[A-Za-z0-9+/]{16,}={0,2}", text)
        for candidate in b64_matches:
            try:
                decoded = base64.b64decode(candidate).decode("utf-8", errors="ignore")
                for name, pattern in self.HIGH_SEVERITY_PATTERNS:
                    if pattern.search(decoded):
                        matched.append(f"OBFUSCATED_BASE64_{name}")
                        score += 0.8
            except Exception:
                pass

        # Normalize score to [0.0, 1.0]
        final_score = min(1.0, round(score, 2))
        is_injected = final_score >= self.threshold

        if final_score >= 0.7:
            risk_level = "CRITICAL" if final_score >= 0.9 else "HIGH"
        elif final_score >= 0.4:
            risk_level = "SUSPICIOUS"
        else:
            risk_level = "SAFE"

        sanitized = self.sanitize_and_wrap(text)

        result = InjectionCheckResult(
            is_injected=is_injected,
            risk_score=final_score,
            risk_level=risk_level,
            matched_patterns=matched,
            sanitized_text=sanitized,
        )

        if strict and is_injected:
            raise SecurityViolationError(
                f"Prompt injection detected ({risk_level}, score={final_score}): {matched}"
            )

        return result

    def sanitize_and_wrap(self, text: str) -> str:
        """Neutralize malicious token delimiters and wrap user input safely."""
        if not text:
            return ""

        sanitized = text
        # Neutralize ChatML, Llama and System tags
        sanitized = re.sub(
            r"<\s*system\s*>", "&lt;system&gt;", sanitized, flags=re.IGNORECASE
        )
        sanitized = re.sub(
            r"<\s*/\s*system\s*>", "&lt;/system&gt;", sanitized, flags=re.IGNORECASE
        )
        sanitized = sanitized.replace("<|im_start|>", "&lt;|im_start|&gt;")
        sanitized = sanitized.replace("<|im_end|>", "&lt;|im_end|&gt;")
        sanitized = sanitized.replace("[INST]", "(INST)").replace("[/INST]", "(/INST)")
        sanitized = sanitized.replace("<<SYS>>", "&lt;&lt;SYS&gt;&gt;").replace(
            "<</SYS>>", "&lt;&lt;/SYS&gt;&gt;"
        )

        # Wrap untrusted text in strict XML sandbox boundary
        return f"<user_untrusted_input>\n{sanitized}\n</user_untrusted_input>"


default_injection_guard = PromptInjectionGuard()
