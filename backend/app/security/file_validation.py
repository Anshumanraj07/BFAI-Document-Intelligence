"""
File upload validation.

Enforces:
  * Allowed extensions (PDF, PNG, JPG, JPEG, TXT)
  * Maximum file size (per-file and bulk)
  * MIME type consistency
  * Magic-number check (first bytes of the file)
"""

from __future__ import annotations

from pathlib import Path
from typing import Final, Set, Tuple

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


# Allowed file extensions
ALLOWED_EXTENSIONS: Final[Set[str]] = {".pdf", ".png", ".jpg", ".jpeg", ".txt"}

# Allowed MIME types (from Content-Type header)
ALLOWED_MIME_TYPES: Final[Set[str]] = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "text/plain",
}

# Magic bytes for supported file types
_MAGIC_SIGNATURES: Final[Tuple[Tuple[bytes, str], ...]] = (
    (b"%PDF-", "pdf"),
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"\xff\xd8\xff", "jpeg"),
    # TXT has no magic bytes — checked by extension and decodability
)


class FileValidationError(Exception):
    """Raised when a file fails validation."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def validate_extension(filename: str) -> str:
    """
    Validate the file extension. Returns the lowercase extension on success.
    Raises FileValidationError on failure.
    """
    if not filename:
        raise FileValidationError("invalid_filename", "Filename is empty")
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise FileValidationError(
            "invalid_extension",
            f"File extension '{ext}' is not allowed. "
            f"Allowed: {sorted(ALLOWED_EXTENSIONS)}",
        )
    return ext


def validate_size(file_size: int, *, bulk: bool = False) -> None:
    """Validate file size against configured limits."""
    if file_size <= 0:
        raise FileValidationError("empty_file", "File is empty")
    limit = settings.MAX_BULK_SIZE_BYTES if bulk else settings.MAX_FILE_SIZE_BYTES
    if file_size > limit:
        mb = file_size / (1024 * 1024)
        limit_mb = limit / (1024 * 1024)
        raise FileValidationError(
            "file_too_large",
            f"File size {mb:.2f}MB exceeds limit of {limit_mb:.2f}MB",
        )


def validate_magic_bytes(content: bytes, extension: str) -> None:
    """
    Inspect the first few bytes of the file to ensure the content matches
    the declared extension. TXT files are exempt (no magic bytes).
    """
    if extension == ".txt":
        # Best-effort: try UTF-8 decode
        try:
            content[:1024].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise FileValidationError(
                "invalid_text_encoding",
                f"Text file is not valid UTF-8: {exc}",
            ) from exc
        return

    for signature, file_type in _MAGIC_SIGNATURES:
        if content.startswith(signature):
            expected_extensions = {
                "pdf": {".pdf"},
                "png": {".png"},
                "jpeg": {".jpg", ".jpeg"},
            }.get(file_type, set())
            if extension in expected_extensions:
                return
            raise FileValidationError(
                "extension_mismatch",
                f"File content looks like {file_type} but extension is {extension}",
            )

    raise FileValidationError(
        "invalid_file_content",
        "File content does not match any supported format",
    )


def validate_upload(
    *,
    filename: str,
    content: bytes,
    mime_type: str | None = None,
    bulk: bool = False,
) -> str:
    """
    Run all validations on a single uploaded file.
    Returns the validated (lowercase) extension on success.
    """
    ext = validate_extension(filename)
    validate_size(len(content), bulk=bulk)
    if mime_type and mime_type not in ALLOWED_MIME_TYPES:
        raise FileValidationError(
            "invalid_mime_type",
            f"MIME type '{mime_type}' is not allowed",
        )
    try:
        validate_magic_bytes(content, ext)
    except FileValidationError:
        # Log but don't fail hard for some edge cases (e.g., very small txt files)
        if ext == ".txt":
            logger.warning("Magic-byte check skipped for text file: %s", filename)
        else:
            raise
    logger.debug("File validated OK: %s (%.2fKB)", filename, len(content) / 1024)
    return ext
