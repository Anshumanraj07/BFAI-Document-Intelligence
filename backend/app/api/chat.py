"""Multi-turn chat endpoint backed by Agentic RAG."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_chatbot, get_db
from app.models.database import ChatMessageORM, ChatSessionORM
from app.models.schemas import ChatRequest, ChatResponse
from app.rag.chatbot import Chatbot
from app.security.api_auth import verify_api_key
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse,
             summary="Multi-turn chat with retrieval-augmented answers")
async def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    chatbot: Chatbot = Depends(get_chatbot),
    _: str = Depends(verify_api_key),
) -> ChatResponse:
    # --- Resolve / create session ---
    session_id = request.session_id or str(uuid.uuid4())
    session = db.get(ChatSessionORM, session_id)
    if not session:
        session = ChatSessionORM(id=session_id, title=request.message[:60])
        db.add(session)
        db.flush()

    # --- Build history for the LLM ---
    history_rows = (
        db.query(ChatMessageORM)
        .filter(ChatMessageORM.session_id == session_id)
        .order_by(ChatMessageORM.created_at.asc())
        .limit(20)
        .all()
    )
    db_history = [{"role": m.role, "content": m.content} for m in history_rows]
    
    # Merge request history with database history (request history takes precedence)
    history = request.history if request.history else db_history

    # --- Persist user message ---
    user_msg = ChatMessageORM(
        session_id=session_id, role="user", content=request.message
    )
    db.add(user_msg)
    db.commit()

    # --- Call the chatbot ---
    try:
        result = await chatbot.ask(
            question=request.message,
            document_ids=request.document_ids,
            top_k=request.top_k,
            chat_history=history,
        )
    except Exception as exc:
        logger.exception("Chat failed: %s", exc)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Chat error: {exc}")

    # --- Persist assistant message ---
    assistant_msg = ChatMessageORM(
        session_id=session_id,
        role="assistant",
        content=result["answer"],
        citations=[c.model_dump() for c in result["citations"]],
        confidence=result["confidence"],
    )
    db.add(assistant_msg)
    db.commit()

    return ChatResponse(
        session_id=session_id,
        answer=result["answer"],
        citations=result["citations"],
        used_documents=result["used_documents"],
        confidence=result["confidence"],
        needs_more_info=result["needs_more_info"],
    )
