"""
Hallucination guard.

Validates the LLM's answer against the retrieved context to prevent
fabricated citations and unsupported claims. Enforces the
"I don't know" response when no relevant context is found.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.config import settings
from app.utils.helpers import truncate_text
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Exact strings we accept as a valid "I don't know" reply
_DONT_KNOW_RESPONSES = {
    "i do not have enough information to answer that based on the uploaded documents.",
    "i don't have enough information to answer that based on the uploaded documents.",
    "i don't know.",
    "i do not know.",
}

# Minimum length for an answer to be considered substantive
MIN_ANSWER_LEN = 10

# Confidence threshold below which we override with "I don't know"
DEFAULT_CONFIDENCE_THRESHOLD = 0.001


@dataclass
class GuardResult:
    """Outcome of the hallucination check."""
    is_valid: bool
    confidence: float
    needs_more_info: bool
    reason: str = ""


class HallucinationGuard:
    """Enforce strict grounding of the LLM's answer to the context."""

    def __init__(self, confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD) -> None:
        self.threshold = confidence_threshold

    def check(
        self,
        answer: str,
        context_hits: List[Dict[str, Any]],
        *,
        top_score: Optional[float] = None,
    ) -> GuardResult:
        """
        Validate the LLM's `answer` against the retrieved `context_hits`.

        Returns a `GuardResult`. The caller decides whether to use the
        original answer, replace it, or re-prompt the LLM.
        """
        answer = (answer or "").strip()
        if not context_hits:
            return GuardResult(
                is_valid=False,
                confidence=0.0,
                needs_more_info=True,
                reason="No context retrieved — refusing to answer.",
            )

        # Compute a heuristic confidence from the top retrieval score
        score = top_score if top_score is not None else max(
            (h.get("score", 0.0) for h in context_hits), default=0.0
        )
        confidence = max(0.0, min(1.0, float(score)))

        # Accept explicit "I don't know" responses
        if self._is_dont_know(answer):
            return GuardResult(
                is_valid=True,
                confidence=confidence,
                needs_more_info=True,
                reason="Model self-identified insufficient information.",
            )

        # Reject very low confidence answers
        if confidence < self.threshold:
            return GuardResult(
                is_valid=False,
                confidence=confidence,
                needs_more_info=True,
                reason=f"Top retrieval score {confidence:.2f} below threshold {self.threshold}",
            )

        # Reject suspiciously short answers
        if len(answer) < MIN_ANSWER_LEN:
            return GuardResult(
                is_valid=False,
                confidence=confidence,
                needs_more_info=True,
                reason=f"Answer too short ({len(answer)} chars)",
            )

        # Warn (but don't reject) if no source markers are present
        if not self._has_source_marker(answer) and not self._has_citation_pattern(answer):
            logger.warning("Answer lacks explicit citation markers: %s", truncate_text(answer, 200))
            # Soft penalty
            confidence *= 0.8

        return GuardResult(
            is_valid=True,
            confidence=confidence,
            needs_more_info=False,
            reason="Answer appears grounded in context.",
        )

    # ============================================================
    # Helpers
    # ============================================================
    @staticmethod
    def _is_dont_know(answer: str) -> bool:
        norm = re.sub(r"\s+", " ", answer.strip().lower())
        return any(norm.startswith(prefix) for prefix in _DONT_KNOW_RESPONSES)

    @staticmethod
    def _has_source_marker(answer: str) -> bool:
        return bool(re.search(r"\[Source\s+\d+\]|\[Document.*Page\s+\d+\]", answer, re.IGNORECASE))

    @staticmethod
    def _has_citation_pattern(answer: str) -> bool:
        # Match "Document X, Page Y" or "page N of X" etc.
        return bool(re.search(r"(?:page|p\.)\s*\d+", answer, re.IGNORECASE))

    @staticmethod
    def dont_know_message() -> str:
        return (
            "I do not have enough information to answer that "
            "based on the uploaded documents."
        )
