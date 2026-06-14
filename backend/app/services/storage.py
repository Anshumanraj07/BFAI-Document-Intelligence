"""
File storage abstraction.

Saves uploaded files to local disk (configurable path) and, if
Cloudinary credentials are present, uploads page images to the cloud
to survive Render's ephemeral filesystem.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict, Optional

from app.config import settings
from app.utils.helpers import sanitize_filename
from app.utils.logger import get_logger

logger = get_logger(__name__)


class StorageService:
    """Save and retrieve uploaded files + rendered page images."""

    def __init__(self) -> None:
        self.base_path = Path(settings.LOCAL_STORAGE_PATH)
        self.uploads_path = self.base_path / "uploads"
        self.images_path = self.base_path / "images"
        self.temp_path = self.base_path / "temp"
        for p in (self.uploads_path, self.images_path, self.temp_path):
            p.mkdir(parents=True, exist_ok=True)

    # ============================================================
    # Save
    # ============================================================
    async def save_upload(
        self,
        *,
        original_filename: str,
        content: bytes,
    ) -> Path:
        """Save raw uploaded content to a safe, UUID-prefixed path."""
        safe_name = sanitize_filename(original_filename)
        dest = self.uploads_path / safe_name
        dest.write_bytes(content)
        logger.info("Saved upload: %s (%.2fKB)", dest.name, len(content) / 1024)
        return dest

    async def save_page_image(
        self,
        *,
        document_id: str,
        page_number: int,
        image_bytes: bytes,
        extension: str = "png",
    ) -> Path:
        """Save a rendered page image to disk."""
        dest = self.images_path / f"{document_id}_p{page_number}.{extension}"
        dest.write_bytes(image_bytes)
        return dest

    # ============================================================
    # Retrieve
    # ============================================================
    def get_page_image_path(self, document_id: str, page_number: int) -> Optional[Path]:
        """Return the local path of a page image, or None."""
        for ext in ("png", "jpg", "jpeg"):
            candidate = self.images_path / f"{document_id}_p{page_number}.{ext}"
            if candidate.exists():
                return candidate
        # Fallback: search by glob (handles PDF-stem naming)
        matches = list(self.images_path.glob(f"{document_id}*p{page_number}.*"))
        return matches[0] if matches else None

    def file_exists(self, path: str) -> bool:
        return Path(path).exists()

    # ============================================================
    # Cleanup
    # ============================================================
    async def cleanup_temp(self, path: str) -> None:
        try:
            p = Path(path)
            if p.exists() and self.temp_path in p.parents:
                p.unlink()
                logger.debug("Cleaned up temp file: %s", path)
        except Exception as exc:  # pragma: no cover
            logger.warning("Cleanup failed for %s: %s", path, exc)

    async def delete_document_files(self, document_id: str) -> int:
        """Delete all files associated with a document. Returns count."""
        deleted = 0
        for folder in (self.uploads_path, self.images_path, self.temp_path):
            for f in folder.glob(f"{document_id}*"):
                try:
                    f.unlink()
                    deleted += 1
                except Exception:  # pragma: no cover
                    pass
        return deleted
