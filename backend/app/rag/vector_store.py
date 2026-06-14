"""
Vector store abstraction over Qdrant Cloud (free tier).

Includes a graceful in-memory fallback so the app still runs in dev
even if Qdrant credentials are not configured (useful for tests).
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from qdrant_client.http.exceptions import UnexpectedResponse

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class VectorStoreError(Exception):
    """Raised on vector-store failures."""
    pass


class VectorStore:
    """Thin wrapper around QdrantClient with safety + fallback."""

    def __init__(self) -> None:
        self.collection_name = settings.QDRANT_COLLECTION_NAME
        self.vector_size = settings.QDRANT_VECTOR_SIZE
        self._client: Optional[QdrantClient] = None
        self._in_memory_fallback: List[Dict[str, Any]] = []
        self._use_fallback = False

    # ============================================================
    # Lifecycle
    # ============================================================
    async def connect(self) -> None:
        """Connect to Qdrant. Falls back to in-memory if connection fails."""
        try:
            if "your-" in settings.QDRANT_API_KEY or "your-" in settings.QDRANT_URL:
                raise ValueError("Qdrant credentials not configured")

            self._client = QdrantClient(
                url=settings.QDRANT_URL,
                api_key=settings.QDRANT_API_KEY,
                timeout=30.0,
            )
            # Verify connectivity
            await asyncio.to_thread(self._client.get_collections)
            await self._ensure_collection()
            logger.info("Connected to Qdrant: %s/%s",
                        settings.QDRANT_URL, self.collection_name)
        except Exception as exc:
            logger.warning(
                "Qdrant unavailable (%s). Falling back to in-memory store.",
                exc,
            )
            self._use_fallback = True
            self._client = None

    async def close(self) -> None:
        if self._client:
            try:
                self._client.close()
            except Exception:  # pragma: no cover
                pass
        self._client = None

    def _ensure_collection(self) -> None:
        """Create the collection if it doesn't exist."""
        try:
            existing = {c.name for c in self._client.get_collections().collections}
        except UnexpectedResponse:
            existing = set()
        if self.collection_name in existing:
            return
        self._client.create_collection(
            collection_name=self.collection_name,
            vectors_config=qmodels.VectorParams(
                size=self.vector_size,
                distance=qmodels.Distance.COSINE,
            ),
        )
        logger.info("Created Qdrant collection: %s", self.collection_name)

    # ============================================================
    # Write
    # ============================================================
    async def insert_chunk(
        self,
        *,
        chunk_id: Optional[str] = None,
        text: str,
        embedding: List[float],
        document_id: str,
        document_name: str,
        page_number: int,
        topic: Optional[str] = None,
        sensitivity_level: Optional[str] = None,
        image_url: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Insert a single text chunk with metadata. Returns the chunk ID."""
        cid = chunk_id or str(uuid.uuid4())
        payload: Dict[str, Any] = {
            "chunk_text": text,
            "document_id": document_id,
            "document_name": document_name,
            "page_number": page_number,
            "topic": topic or "",
            "sensitivity_level": sensitivity_level or "Low",
            "image_url": image_url or "",
        }
        if extra:
            payload.update(extra)

        if self._use_fallback:
            payload["_id"] = cid
            payload["_vector"] = embedding
            self._in_memory_fallback.append(payload)
            return cid

        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                lambda: self._client.upsert(
                    collection_name=self.collection_name,
                    points=[qmodels.PointStruct(
                        id=cid, vector=embedding, payload=payload,
                    )],
                ),
            )
            return cid
        except Exception as exc:
            logger.exception("Failed to insert chunk: %s", exc)
            raise VectorStoreError(str(exc)) from exc

    async def insert_chunks_bulk(
        self,
        chunks: List[Dict[str, Any]],
    ) -> List[str]:
        """Insert many chunks at once. Each chunk dict must have `embedding` and `text`."""
        ids: List[str] = []
        for chunk in chunks:
            cid = await self.insert_chunk(**chunk)
            ids.append(cid)
        return ids

    # ============================================================
    # Read
    # ============================================================
    async def search(
        self,
        *,
        query_embedding: List[float],
        top_k: int = 5,
        document_ids: Optional[List[str]] = None,
        score_threshold: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Return the top-k most similar chunks, optionally filtered by document."""
        if self._use_fallback:
            return self._search_fallback(query_embedding, top_k, document_ids, score_threshold)

        try:
            loop = asyncio.get_running_loop()

            # Build filter
            qfilter = None
            if document_ids:
                qfilter = qmodels.Filter(must=[
                    qmodels.FieldCondition(
                        key="document_id",
                        match=qmodels.MatchAny(any=document_ids),
                    )
                ])

            def _do_search() -> List[Any]:
                return self._client.search(
                    collection_name=self.collection_name,
                    query_vector=query_embedding,
                    limit=top_k,
                    query_filter=qfilter,
                    score_threshold=score_threshold,
                    with_payload=True,
                    with_vectors=False,
                )

            hits = await loop.run_in_executor(None, _do_search)
            return [
                {
                    "id": str(h.id),
                    "score": float(h.score),
                    "payload": dict(h.payload or {}),
                }
                for h in hits
            ]
        except Exception as exc:
            logger.exception("Vector search failed: %s", exc)
            return []

    def _search_fallback(
        self,
        query_embedding: List[float],
        top_k: int,
        document_ids: Optional[List[str]],
        score_threshold: Optional[float],
    ) -> List[Dict[str, Any]]:
        """Cosine similarity over the in-memory store."""
        import numpy as np

        if not self._in_memory_fallback:
            return []
        q = np.asarray(query_embedding, dtype=np.float32)
        results: List[Dict[str, Any]] = []
        for item in self._in_memory_fallback:
            if document_ids and item.get("document_id") not in document_ids:
                continue
            v = np.asarray(item.pop("_vector", []), dtype=np.float32)
            if v.size == 0 or v.shape != q.shape:
                continue
            denom = (np.linalg.norm(q) * np.linalg.norm(v)) or 1e-9
            score = float(np.dot(q, v) / denom)
            if score_threshold is not None and score < score_threshold:
                continue
            results.append({
                "id": item.get("_id", ""),
                "score": score,
                "payload": {k: val for k, val in item.items() if not k.startswith("_")},
            })
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    async def get_by_document_id(self, document_id: str) -> List[Dict[str, Any]]:
        """Return all chunks belonging to a document (used for deletion/list)."""
        if self._use_fallback:
            return [c for c in self._in_memory_fallback if c.get("document_id") == document_id]
        try:
            loop = asyncio.get_running_loop()
            def _scroll():
                return self._client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=qmodels.Filter(must=[
                        qmodels.FieldCondition(
                            key="document_id",
                            match=qmodels.MatchValue(value=document_id),
                        )
                    ]),
                    limit=1000,
                    with_payload=True,
                    with_vectors=False,
                )
            records, _ = await loop.run_in_executor(None, _scroll)
            return [{"id": str(r.id), "payload": dict(r.payload or {})} for r in records]
        except Exception as exc:
            logger.exception("Scroll by document_id failed: %s", exc)
            return []

    async def delete_by_document_id(self, document_id: str) -> int:
        """Delete all chunks for a document. Returns count deleted."""
        if self._use_fallback:
            before = len(self._in_memory_fallback)
            self._in_memory_fallback = [
                c for c in self._in_memory_fallback if c.get("document_id") != document_id
            ]
            return before - len(self._in_memory_fallback)
        try:
            loop = asyncio.get_running_loop()
            def _do_delete():
                return self._client.delete(
                    collection_name=self.collection_name,
                    points_selector=qmodels.FilterSelector(filter=qmodels.Filter(must=[
                        qmodels.FieldCondition(
                            key="document_id",
                            match=qmodels.MatchValue(value=document_id),
                        )
                    ])),
                )
            await loop.run_in_executor(None, _do_delete)
            return 0  # Qdrant doesn't return count
        except Exception as exc:
            logger.exception("Delete failed: %s", exc)
            return 0

    @property
    def is_using_fallback(self) -> bool:
        return self._use_fallback


# ============================================================
# Singleton accessor
# ============================================================
_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """Return the process-wide vector store instance."""
    global _store
    if _store is None:
        _store = VectorStore()
    return _store
