"""
LLM-based document classifier.

Uses **Groq** (Llama 3) as the primary provider for speed on bulk uploads,
with **Gemini** as a fallback. Enforces the JSON schema defined in
`schema.py` via Pydantic validation.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

import httpx
from groq import AsyncGroq

from app.classifiers.schema import (
    CLASSIFIER_SYSTEM_PROMPT,
    ClassificationOutput,
    validate_classification,
)
from app.config import settings
from app.utils.helpers import truncate_text
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ClassifierError(Exception):
    """Raised when classification fails irrecoverably."""
    pass


class DocumentClassifier:
    """Classify parsed document text into a structured JSON object."""

    def __init__(
        self,
        *,
        primary_provider: str = "groq",
        timeout: float = 30.0,
    ) -> None:
        self.primary = primary_provider
        self.timeout = timeout
        self._groq: Optional[AsyncGroq] = None
        if settings.GROQ_API_KEY and "your-" not in settings.GROQ_API_KEY:
            self._groq = AsyncGroq(api_key=settings.GROQ_API_KEY, timeout=timeout)

    # ============================================================
    # Public API
    # ============================================================
    async def classify(self, text: str) -> ClassificationOutput:
        """
        Classify `text` and return a validated `ClassificationOutput`.
        Falls back across providers on failure.
        """
        if not text or not text.strip():
            raise ClassifierError("Cannot classify empty text")

        truncated = truncate_text(text, max_chars=6000)
        last_error: Optional[Exception] = None

        # Try primary provider, then fallbacks
        providers = [self.primary] + [p for p in ("groq", "gemini") if p != self.primary]
        for provider in providers:
            try:
                logger.debug("Classifying with provider=%s (len=%d)", provider, len(truncated))
                raw = await self._call_provider(provider, truncated)
                validated = self._parse_and_validate(raw)
                logger.info(
                    "Classification OK (%s): type=%s topic='%s' conf=%.2f",
                    provider, validated.document_type, validated.topic, validated.confidence,
                )
                return validated
            except Exception as exc:
                logger.warning("Provider %s failed: %s", provider, exc)
                last_error = exc

        raise ClassifierError(f"All classifier providers failed: {last_error}")

    # ============================================================
    # Provider calls
    # ============================================================
    async def _call_provider(self, provider: str, text: str) -> str:
        if provider == "groq":
            return await self._call_groq(text)
        if provider == "gemini":
            return await self._call_gemini(text)
        raise ClassifierError(f"Unknown provider: {provider}")

    async def _call_groq(self, text: str) -> str:
        if not self._groq:
            raise ClassifierError("Groq client not configured (missing API key)")
        response = await self._groq.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": CLASSIFIER_SYSTEM_PROMPT},
                {"role": "user", "content": f"Classify this document:\n\n{text}"},
            ],
            temperature=0.0,
            max_tokens=400,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content or ""

    async def _call_gemini(self, text: str) -> str:
        if not settings.GEMINI_API_KEY or "your-" in settings.GEMINI_API_KEY:
            raise ClassifierError("Gemini API key not configured")

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{settings.GEMINI_MODEL}:generateContent?key={settings.GEMINI_API_KEY}"
        )
        payload = {
            "contents": [{
                "parts": [{
                    "text": f"{CLASSIFIER_SYSTEM_PROMPT}\n\nClassify this document:\n\n{text}"
                }]
            }],
            "generationConfig": {
                "temperature": 0.0,
                "maxOutputTokens": 400,
                "responseMimeType": "application/json",
            },
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(url, json=payload)
            r.raise_for_status()
            data = r.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as exc:
            raise ClassifierError(f"Unexpected Gemini response: {data}") from exc

    # ============================================================
    # Validation
    # ============================================================
    def _parse_and_validate(self, raw: str) -> ClassificationOutput:
        """Parse the LLM's raw string and validate against the schema."""
        if not raw or not raw.strip():
            raise ClassifierError("LLM returned empty response")
        # Strip any code fences (defensive)
        cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
        try:
            obj = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ClassifierError(f"LLM did not return valid JSON: {exc}\nRaw: {raw[:200]}") from exc
        if not isinstance(obj, dict):
            raise ClassifierError(f"Expected JSON object, got {type(obj).__name__}")
        return validate_classification(obj)
