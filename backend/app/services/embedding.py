"""
Embedding service.

Primary: Google Gemini (`models/embedding-001`) — free, no local model.
The class is designed to be swapped out for `sentence-transformers`
or any other provider with a single method override.
"""

from __future__ import annotations

import hashlib
from typing import List

import httpx
import numpy as np

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class EmbeddingService:
    """Generate dense vector embeddings for text."""

    def __init__(self, *, expected_dim: int | None = None) -> None:
        self.expected_dim = expected_dim or settings.QDRANT_VECTOR_SIZE
        self._timeout = 30.0

    async def embed_query(self, text: str) -> List[float]:
        """Embed a single query string."""
        vectors = await self.embed_texts([text])
        return vectors[0] if vectors else []

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Embed a batch of texts. Returns a list of vectors (each length = expected_dim).
        Falls back to a deterministic hash-based vector if Gemini is unavailable.
        """
        cleaned = [t.strip() for t in texts if t and t.strip()]
        if not cleaned:
            return []

        if not settings.GEMINI_API_KEY or "your-" in settings.GEMINI_API_KEY:
            logger.warning("Gemini not configured — using fallback embeddings")
            return [self._fallback_embed(t) for t in cleaned]

        try:
            return await self._embed_gemini_batch(cleaned)
        except Exception as exc:
            logger.exception("Gemini embedding failed, using fallback: %s", exc)
            return [self._fallback_embed(t) for t in cleaned]

    # ============================================================
    # Gemini batch embed
    # ============================================================
    async def _embed_gemini_batch(self, texts: List[str]) -> List[List[float]]:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/"
            f"{settings.GEMINI_EMBEDDING_MODEL}:batchEmbedContents?key={settings.GEMINI_API_KEY}"
        )
        # Gemini accepts up to 100 requests per batch
        all_vectors: List[List[float]] = []
        batch_size = 100

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for i in range(0, len(texts), batch_size):
                batch = texts[i: i + batch_size]
                payload = {
                    "requests": [
                        {
                            "model": settings.GEMINI_EMBEDDING_MODEL,
                            "content": {"parts": [{"text": t}]},
                            "taskType": "RETRIEVAL_DOCUMENT",
                        }
                        for t in batch
                    ]
                }
                r = await client.post(url, json=payload)
                r.raise_for_status()
                data = r.json()
                for emb in data.get("embeddings", []):
                    vec = emb.get("values", [])
                    # Pad/truncate to expected_dim
                    vec = self._normalize_dim(vec)
                    all_vectors.append(vec)
        logger.debug("Embedded %d texts via Gemini", len(all_vectors))
        return all_vectors

    # ============================================================
    # Fallback (deterministic hash-based)
    # ============================================================
    def _fallback_embed(self, text: str) -> List[float]:
        """
        Deterministic, low-quality embedding for dev/testing without API.
        WARNING: Not semantically meaningful. Only useful for verifying
        the pipeline end-to-end.
        """
        rng = np.random.default_rng(
            int(hashlib.md5(text.encode("utf-8")).hexdigest(), 16) % (2**32)
        )
        v = rng.standard_normal(self.expected_dim).astype(np.float32)
        v /= (np.linalg.norm(v) + 1e-9)
        return v.tolist()

    def _normalize_dim(self, vec: List[float]) -> List[float]:
        if len(vec) == self.expected_dim:
            return vec
        if len(vec) > self.expected_dim:
            return vec[: self.expected_dim]
        return vec + [0.0] * (self.expected_dim - len(vec))
