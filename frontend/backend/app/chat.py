"""
Chat endpoint backed by RAG.
"""

from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    document_ids: Optional[List[str]] = None
    top_k: Optional[int] = 5


class Citation(BaseModel):
    doc: str
    page: int


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    citations: List[Citation]
    used_documents: Optional[List[str]] = None
    confidence: Optional[float] = None
    needs_more_info: Optional[bool] = None


# Mock session storage
sessions_db = {}


@router.post("/chat", response_model=ChatResponse, summary="Multi-turn chat with retrieval-augmented answers")
async def chat(request: ChatRequest) -> ChatResponse:
    session_id = request.session_id or str(uuid.uuid4())

    # Mock response for frontend integration
    answer = f"Based on the uploaded documents, here's what I found regarding your question about '{request.message[:50]}...':\n\nThe relevant information appears across multiple sections. Key points include:\n\n1. The document outlines important procedures and guidelines\n2. Several references mention the topic in question\n3. Additional context is available in the cited sources below."

    # Mock citations
    citations = [
        Citation(doc="sample_document.pdf", page=1),
        Citation(doc="sample_document.pdf", page=3),
    ]

    return ChatResponse(
        session_id=session_id,
        answer=answer,
        citations=citations,
        used_documents=["sample_document.pdf"],
        confidence=0.85,
        needs_more_info=False,
    )
