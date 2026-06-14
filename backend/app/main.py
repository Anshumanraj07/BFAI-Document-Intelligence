"""
FastAPI application entry point.

Wires up:
  * CORS, logging, rate-limiting middleware
  * All API routers (upload, classify, chat, documents, voice)
  * Startup/shutdown lifecycle (DB init, vector store connect)
  * Health check + global exception handlers
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

# CORS Middleware (ONLY ONE - allow all origins for demo)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (for demo)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiter
app.state.limiter = limiter
from app.security.api_auth import limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Request-logging middleware
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

# Exception handlers
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

# Health check
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

# Routers
app.include_router(upload.router)
app.include_router(classify.router)
app.include_router(chat.router)
app.include_router(documents.router)
app.include_router(voice.router)

# Root
@app.get("/", include_in_schema=False)
async def root():
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health",
    }