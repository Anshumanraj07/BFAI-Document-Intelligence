# Replace ENTIRE main.py with this:

"""
FastAPI application entry point.

Wires up:
  * CORS, logging, rate-limiting middleware
  * All API routers (upload, classify, chat, documents, voice)
  * Startup/shutdown lifecycle (DB init, vector store connect)
  * Health check + global exception handlers
  * Chat endpoint (POST /api/chat)
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional


from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware


from app.api import chat, classify, documents, upload, voice
from app.config import settings
from app.models.database import init_db
from app.rag.vector_store import get_vector_store
from app.rag.retriever import Retriever
from app.rag.chatbot import Chatbot
from app.services.embedding import EmbeddingService
from app.security.api_auth import limiter
from app.utils.logger import get_logger, logger


# ============================================================
# Lifespan
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup + shutdown hooks."""
    logger.info("=" * 60)
    logger.info("Starting %s v%s (env=%s)",
                settings.APP_NAME, settings.APP_VERSION, settings.APP_ENV)
    logger.info("=" * 60)

    # Init DB tables
    try:
        init_db()
    except Exception as exc:
        logger.exception("DB init failed: %s", exc)

    # Connect vector store
    vs = get_vector_store()
    await vs.connect()
    if vs.is_using_fallback:
        logger.warning("⚠️  Vector store running in IN-MEMORY FALLBACK mode "
                      "(configure Qdrant in .env for production).")
    else:
        logger.info("Vector store ready: %s", settings.QDRANT_COLLECTION_NAME)

    logger.info("Application startup complete.")
    yield

    # Shutdown
    await vs.close()
    logger.info("Application shutdown complete.")


# ============================================================
# App factory
# ============================================================
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Document Parser + LLM Classifier + Agentic RAG Chatbot — "
        "BFAI AI Engineer Intern Assessment."
    ),
    debug=settings.APP_DEBUG,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


# Rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Request-logging middleware
# ============================================================
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "%s %s -> %d (%.1fms)",
        request.method, request.url.path, response.status_code, duration_ms,
    )
    return response


# ============================================================
# Exception handlers
# ============================================================
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s: %s",
                    request.method, request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": {
            "code": "internal_error",
            "message": "An internal error occurred. Please try again.",
        }},
    )


# ============================================================
# Health check
# ============================================================
@app.get("/health", tags=["health"], summary="Service health check")
async def health() -> Dict[str, Any]:
    vs = get_vector_store()
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "env": settings.APP_ENV,
        "vector_store": "fallback" if vs.is_using_fallback else "qdrant",
    }


# ============================================================
# Chat Endpoint
# ============================================================
from pydantic import BaseModel


# Request schema
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    document_ids: Optional[List[str]] = None


@app.post("/api/chat", tags=["chat"], summary="RAG chatbot query")
async def chat_endpoint(body: ChatRequest) -> Dict[str, Any]:
    """
    Agentic RAG chatbot query.
    """
    try:
        message = body.message
        session_id = body.session_id
        document_ids = body.document_ids
        
        # Initialize components (CORRECT ORDER)
        vs = get_vector_store()
        embedding_service = EmbeddingService()  # ← Define FIRST!
        retriever = Retriever(vs, embedding_service)  # ← Use AFTER!
        chatbot = Chatbot(retriever, embedding_service)
        
        # No chat history
        chat_history = []
        
        # Ask chatbot
        result = await chatbot.ask(
            question=message,
            document_ids=document_ids,
            top_k=5,
            chat_history=chat_history,
        )
        
        # Return response
        return {
            "answer": result["answer"],
            "citations": [
                {"doc": c.document_name, "page": c.page_number}
                for c in result["citations"]
            ],
            "session_id": session_id,
            "confidence": result["confidence"],
        }
        
    except Exception as exc:
        logger.exception("Chat endpoint failed: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "chat_error",
                    "message": f"Chatbot error: {str(exc)}",
                }
            },
        )
    
    
# ============================================================
# Routers
# ============================================================
app.include_router(upload.router)
app.include_router(classify.router)
app.include_router(chat.router)
app.include_router(documents.router)
app.include_router(voice.router)


# ============================================================
# Root
# ============================================================
@app.get("/", include_in_schema=False)
async def root():
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health",
    }