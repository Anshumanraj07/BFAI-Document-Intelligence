"""
Shared FastAPI dependencies.

Centralises service singletons so route handlers can pull them in
via `Depends()` and remain easy to mock in tests.
"""

from __future__ import annotations

from functools import lru_cache
from typing import AsyncGenerator

from fastapi import Depends
from sqlalchemy.orm import Session

from app.classifiers.document_classifier import DocumentClassifier
from app.config import settings
from app.models.database import SessionLocal
from app.rag.chatbot import Chatbot
from app.rag.hallucination_guard import HallucinationGuard
from app.rag.retriever import Retriever
from app.rag.vector_store import VectorStore, get_vector_store
from app.services.embedding import EmbeddingService
from app.services.processing import ProcessingPipeline
from app.services.storage import StorageService


# ============================================================
# DB session dependency
# ============================================================
def get_db() -> AsyncGenerator[Session, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================
# Service singletons
# ============================================================
@lru_cache
def get_storage() -> StorageService:
    return StorageService()


@lru_cache
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()


@lru_cache
def get_classifier() -> DocumentClassifier:
    return DocumentClassifier()


@lru_cache
def get_hallucination_guard() -> HallucinationGuard:
    return HallucinationGuard()


def get_vector_store_dep() -> VectorStore:
    return get_vector_store()


def get_retriever(
    vs: VectorStore = Depends(get_vector_store_dep),
    emb: EmbeddingService = Depends(get_embedding_service),
) -> Retriever:
    return Retriever(vs, emb)


def get_chatbot(
    retriever: Retriever = Depends(get_retriever),
    emb: EmbeddingService = Depends(get_embedding_service),
    guard: HallucinationGuard = Depends(get_hallucination_guard),
) -> Chatbot:
    return Chatbot(retriever, emb, guard)


def get_pipeline(
    vs: VectorStore = Depends(get_vector_store_dep),
    emb: EmbeddingService = Depends(get_embedding_service),
    storage: StorageService = Depends(get_storage),
    classifier: DocumentClassifier = Depends(get_classifier),
) -> ProcessingPipeline:
    return ProcessingPipeline(
        vector_store=vs, embedding_service=emb,
        storage=storage, classifier=classifier,
    )
