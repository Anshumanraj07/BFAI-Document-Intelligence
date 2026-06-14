"""
Retriever: builds query embeddings, calls the vector store, and
returns clean, citation-ready context chunks.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.config import settings
from app.rag.vector_store import VectorStore
from app.services.embedding import EmbeddingService
from app.utils.logger import get_logger

logger = get_logger(__name__)


class Retriever:
    """Similarity search wrapper that produces context chunks."""

    def __init__(
        self,
        vector_store: VectorStore,
        embedding_service: EmbeddingService,
        default_top_k: int = 10,
    ) -> None:
        self.vector_store = vector_store
        self.embeddings = embedding_service
        self.default_top_k = default_top_k

    async def retrieve(
        self,
        query: str,
        *,
        top_k: Optional[int] = None,
        document_ids: Optional[List[str]] = None,
        score_threshold: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Embed the query, search the vector store, and return ranked chunks.

        Returns a list of dicts with `score`, `chunk_text`, and metadata
        (document_id, document_name, page_number, image_url, etc.).
        """
        if not query or not query.strip():
            return []

        k = top_k or self.default_top_k
        query_embedding = await self.embeddings.embed_query(query)
        if not query_embedding:
            logger.warning("Empty embedding returned; skipping search")
            return []

        hits = await self.vector_store.search(
            query_embedding=query_embedding,
            top_k=k,
            document_ids=document_ids,
            score_threshold=score_threshold,
        )
        logger.info("Retrieved %d chunks (k=%d, filter=%s)",
                    len(hits), k, document_ids or "none")
        return hits

    @staticmethod
    def format_context(hits: List[Dict[str, Any]], max_chars: int = 6000) -> str:
        """
        Format retrieved chunks into a single context string for the LLM.
        Includes explicit `[Source N]` markers for easy citation.
        """
        parts: List[str] = []
        used = 0
        for i, h in enumerate(hits, start=1):
            payload = h.get("payload", {}) or {}
            text = (payload.get("chunk_text") or "").strip()
            doc_name = payload.get("document_name", "Unknown")
            page = payload.get("page_number", "?")
            block = f"[Source {i}] Document: {doc_name} | Page: {page}\n{text}\n"
            if used + len(block) > max_chars:
                break
            parts.append(block)
            used += len(block)
        return "\n---\n".join(parts)
