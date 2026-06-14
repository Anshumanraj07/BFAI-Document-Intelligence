"""
JSON schema for the LLM classifier output.

We use Pydantic v2 models (not raw JSON Schema strings) so that
both runtime validation and OpenAPI generation are automatic.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict

from pydantic import BaseModel, Field, field_validator


class DocumentTypeEnum(str, Enum):
    INVOICE = "invoice"
    REPORT = "report"
    CONTRACT = "contract"
    RESUME = "resume"
    RECEIPT = "receipt"
    OTHER = "other"


class SensitivityLevelEnum(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class ClassificationOutput(BaseModel):
    """Strict schema the LLM must conform to."""

    document_type: DocumentTypeEnum = DocumentTypeEnum.OTHER
    topic: str = Field(default="Unknown", max_length=255)
    is_sensitive: bool = False
    sensitivity_level: SensitivityLevelEnum = SensitivityLevelEnum.LOW
    language: str = Field(default="en", min_length=2, max_length=10)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reasoning: str | None = Field(default=None, description="LLM's chain-of-thought")

    @field_validator("language")
    @classmethod
    def _norm_lang(cls, v: str) -> str:
        return (v or "en").strip().lower()[:10]

    @field_validator("topic")
    @classmethod
    def _norm_topic(cls, v: str) -> str:
        v = (v or "").strip()
        return v[:255] if v else "Unknown"


# System prompt fragment used to instruct the LLM to return valid JSON
CLASSIFIER_SYSTEM_PROMPT = """You are a document classification assistant.
You MUST respond with a single valid JSON object — no prose, no markdown.

Schema:
{
  "document_type": one of ["invoice", "report", "contract", "resume", "receipt", "other"],
  "topic": "Short descriptive topic (max 255 chars)",
  "is_sensitive": true | false,   // contains PII, financial secrets, or confidential data
  "sensitivity_level": "Low" | "Medium" | "High",
  "language": "ISO-639-1 two-letter code, e.g. 'en', 'es', 'fr'",
  "confidence": number between 0.0 and 1.0
}

Rules:
- Output ONLY the JSON. No backticks, no commentary.
- If uncertain, use "other" and set confidence below 0.5.
- 'is_sensitive' is true for invoices with totals > $1000, contracts, resumes, medical, or financial docs.
"""


def validate_classification(raw: Dict[str, Any]) -> ClassificationOutput:
    """
    Validate a raw dict (e.g., from an LLM response) against the schema.
    Raises pydantic.ValidationError on failure.
    """
    return ClassificationOutput.model_validate(raw)
