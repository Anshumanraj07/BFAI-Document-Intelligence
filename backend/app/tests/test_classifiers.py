"""Unit tests for the classifier (mocked LLM responses)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.classifiers.document_classifier import DocumentClassifier
from app.classifiers.schema import ClassificationOutput, validate_classification


def test_validate_classification_accepts_valid_dict():
    raw = {
        "document_type": "invoice",
        "topic": "Q3 SaaS subscription",
        "is_sensitive": True,
        "sensitivity_level": "Medium",
        "language": "en",
        "confidence": 0.92,
    }
    result = validate_classification(raw)
    assert result.document_type.value == "invoice"
    assert result.is_sensitive is True
    assert 0.0 <= result.confidence <= 1.0


def test_validate_classification_rejects_invalid_type():
    with pytest.raises(Exception):
        validate_classification({"document_type": "novel", "topic": "x"})


@pytest.mark.asyncio
async def test_classify_uses_groq(monkeypatch):
    fake_response = json.dumps({
        "document_type": "report",
        "topic": "Annual Financial Report",
        "is_sensitive": False,
        "sensitivity_level": "Low",
        "language": "en",
        "confidence": 0.88,
    })

    classifier = DocumentClassifier()

    mock_groq = AsyncMock()
    mock_groq.chat.completions.create = AsyncMock(
        return_value=type("R", (), {"choices": [
            type("C", (), {"message": type("M", (), {"content": fake_response})()})()
        ]})()
    )
    monkeypatch.setattr(classifier, "_groq", mock_groq)

    result = await classifier.classify("Annual revenue grew by 12%...")
    assert result.document_type.value == "report"
    assert result.topic.startswith("Annual")
    assert result.confidence > 0.5


@pytest.mark.asyncio
async def test_classify_handles_empty_text():
    classifier = DocumentClassifier()
    from app.classifiers.document_classifier import ClassifierError
    with pytest.raises(ClassifierError):
        await classifier.classify("")
