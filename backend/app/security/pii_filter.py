"""
PII (Personally Identifiable Information) detection and redaction.

Uses regex-based pattern matching for emails, phone numbers, SSNs, and
credit-card numbers. Designed for the "Processing Layer" security requirement.
For production-grade PII detection, swap in Microsoft Presidio.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Pattern, Tuple

from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class PIIMatch:
    """A single PII occurrence."""
    pii_type: str
    value: str
    start: int
    end: int


# ============================================================
# Patterns
# ============================================================
_PATTERNS: List[Tuple[str, Pattern[str]]] = [
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")),
    ("PHONE", re.compile(
        r"\b(?:\+?1[\s\-.]?)?\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}\b"
    )),
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("CREDIT_CARD", re.compile(r"\b(?:\d{4}[\s\-]?){3}\d{4}\b")),
    ("IP_ADDRESS", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    # IBAN (basic)
    ("IBAN", re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b")),
]


_REDACTION_TEMPLATES = {
    "EMAIL": "[REDACTED_EMAIL]",
    "PHONE": "[REDACTED_PHONE]",
    "SSN": "[REDACTED_SSN]",
    "CREDIT_CARD": "[REDACTED_CC]",
    "IP_ADDRESS": "[REDACTED_IP]",
    "IBAN": "[REDACTED_IBAN]",
}


# ============================================================
# Public API
# ============================================================
def detect_pii(text: str) -> List[PIIMatch]:
    """Return all PII matches found in `text`."""
    if not text:
        return []
    matches: List[PIIMatch] = []
    for pii_type, pattern in _PATTERNS:
        for m in pattern.finditer(text):
            matches.append(PIIMatch(pii_type, m.group(0), m.start(), m.end()))
    return matches


def redact_text(text: str, *, replacement: str | None = None) -> str:
    """
    Replace all detected PII in `text` with redaction placeholders.
    Returns the redacted string.
    """
    if not text:
        return text
    redacted = text
    for pii_type, pattern in _PATTERNS:
        token = replacement or _REDACTION_TEMPLATES[pii_type]
        redacted = pattern.sub(token, redacted)
    return redacted


def contains_pii(text: str) -> bool:
    """Quick boolean check: does `text` contain any PII?"""
    return bool(detect_pii(text))


def redact_dict_values(data: dict) -> dict:
    """Recursively redact string values in a dict (best-effort, shallow)."""
    if not isinstance(data, dict):
        return data
    out = {}
    for k, v in data.items():
        if isinstance(v, str):
            out[k] = redact_text(v)
        elif isinstance(v, dict):
            out[k] = redact_dict_values(v)
        elif isinstance(v, list):
            out[k] = [redact_text(i) if isinstance(i, str) else i for i in v]
        else:
            out[k] = v
    return out
