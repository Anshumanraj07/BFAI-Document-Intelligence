"""
FastAPI main application entry point.
Configures CORS for frontend integration.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

# CORS origins from environment
CORS_ORIGINS = os.getenv(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:9091,http://127.0.0.1:3000"
).split(",")

app = FastAPI(
    title="BFAI Document AI",
    description="Document parsing, classification, and RAG chatbot API",
    version="1.0.0",
)

# Configure CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-API-Key",
        "Accept",
    ],
)

# Import routers from existing backend modules
try:
    from app.upload import router as upload_router
    from app.chat import router as chat_router
    from app.documents import router as documents_router

    app.include_router(upload_router)
    app.include_router(chat_router)
    app.include_router(documents_router)
except ImportError:
    # Routers will be added when backend is fully set up
    pass


@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "healthy", "service": "BFAI Document AI"}


@app.get("/", tags=["root"])
async def root():
    return {
        "message": "BFAI Document AI API",
        "docs": "/docs",
        "health": "/health",
    }
