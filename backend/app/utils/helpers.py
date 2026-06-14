"""General utility functions used across the application."""

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from app.utils.logger import get_logger

logger = get_logger(__name__)


def generate_uuid() -> str:
    """Generate a new UUID4 string."""
    return str(uuid.uuid4())


def generate_short_id(length: int = 8) -> str:
    """Generate a short, URL-safe ID."""
    return uuid.uuid4().hex[:length]


def utc_now() -> datetime:
    """Return the current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    """Return the current UTC datetime as an ISO-8601 string."""
    return utc_now().isoformat()


def sanitize_filename(filename: str) -> str:
    """
    Strip path components and dangerous characters from a filename.
    Returns a safe, UUID-prefixed name to prevent directory traversal.
    """
    if not filename:
        return f"{generate_short_id()}_unnamed"
    # Strip directory parts
    base = Path(filename).name
    # Replace unsafe characters
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", base)
    return f"{generate_short_id()}_{safe}"


def compute_file_hash(content: bytes) -> str:
    """Return the SHA-256 hex digest of file content (for deduplication)."""
    return hashlib.sha256(content).hexdigest()


def truncate_text(text: str, max_chars: int = 4000) -> str:
    """Safely truncate text for LLM context windows."""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 50] + "\n\n[...truncated for length...]"


def chunk_text(
    text: str,
    chunk_size: int = 800,
    chunk_overlap: int = 100,
) -> list[str]:
    """
    Split a long text into overlapping chunks for embedding.

    Uses a simple sliding-window approach (character-level) to avoid
    the heavy `langchain` dependency. Suitable for most document types.
    """
    if not text or not text.strip():
        return []
    text = text.strip()
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(text):
            break
        start += chunk_size - chunk_overlap
    logger.debug("Chunked %d chars into %d chunks", len(text), len(chunks))
    return chunks


def safe_get(d: Optional[Dict[str, Any]], *keys: str, default: Any = None) -> Any:
    """Safely traverse nested dicts without raising KeyError."""
    current: Any = d
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current
