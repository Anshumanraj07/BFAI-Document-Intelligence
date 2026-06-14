"""Unit tests for the RAG pipeline (vector store, retriever, guard, chatbot)."""

from __future__ import annotations

import pytest

from app.rag.hallucination_guard import HallucinationGuard


def test_guard_rejects_when_no_context():
    guard = HallucinationGuard()
    result = guard.check("The answer is 42.", context_hits=[], top_score=0.0)
    assert result.is_valid is False
    assert result.needs_more_info is True


def test_guard_accepts_dont_know_response():
    guard = HallucinationGuard()
    hits = [{"score": 0.3, "payload": {"chunk_text": "foo", "document_name": "a.pdf",
                                      "page_number": 1, "document_id": "d1"}}]
    answer = "I do not have enough information to answer that based on the uploaded documents."
    result = guard.check(answer, hits, top_score=0.3)
    assert result.is_valid is True
    assert result.needs_more_info is True


def test_guard_rejects_low_confidence():
    guard = HallucinationGuard(confidence_threshold=0.5)
    hits = [{"score": 0.1, "payload": {"chunk_text": "foo", "document_name": "a.pdf",
                                      "page_number": 1, "document_id": "d1"}}]
    result = guard.check("Some answer", hits, top_score=0.1)
    assert result.is_valid is False


def test_guard_accepts_grounded_answer():
    guard = HallucinationGuard(confidence_threshold=0.3)
    hits = [{"score": 0.9, "payload": {"chunk_text": "Revenue was $4.2M",
                                       "document_name": "Q3.pdf", "page_number": 4,
                                       "document_id": "d1"}}]
    answer = "Revenue was $4.2M. [Document: Q3.pdf, Page: 4]"
    result = guard.check(answer, hits, top_score=0.9)
    assert result.is_valid is True
    assert result.confidence > 0.5


def test_dont_know_message_format():
    msg = HallucinationGuard.dont_know_message()
    assert "do not have enough information" in msg.lower()
