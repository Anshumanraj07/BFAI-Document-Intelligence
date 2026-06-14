"""
Voice transcription endpoint.

Accepts an audio file (webm/wav/mp3/m4a) and returns the transcribed
text via Groq's free Whisper API.
"""

from __future__ import annotations

import io
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from groq import AsyncGroq

from app.config import settings
from app.security.api_auth import verify_api_key
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/voice", tags=["voice"])


_ALLOWED_AUDIO_EXT = {".webm", ".wav", ".mp3", ".m4a", ".ogg", ".flac"}
_MAX_AUDIO_BYTES = 25 * 1024 * 1024  # 25 MB


@router.post("/transcribe", summary="Transcribe audio to text via Groq Whisper")
async def transcribe_audio(
    audio: UploadFile = File(..., description="Audio file (webm, wav, mp3, m4a)"),
    language: str | None = None,
    _: str = Depends(verify_api_key),
):
    if not audio.filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Missing filename")

    ext = Path(audio.filename).suffix.lower()
    if ext not in _ALLOWED_AUDIO_EXT:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Unsupported audio format: {ext}. Allowed: {sorted(_ALLOWED_AUDIO_EXT)}",
        )

    content = await audio.read()
    if len(content) > _MAX_AUDIO_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Audio too large (max 25MB)")
    if not content:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty audio file")

    if not settings.GROQ_API_KEY or "your-" in settings.GROQ_API_KEY:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Groq API key not configured")

    try:
        # Write to a temp file (Whisper needs a file-like object with a name)
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        with open(tmp_path, "rb") as f:
            transcription = await client.audio.transcriptions.create(
                file=(audio.filename, f.read()),
                model=settings.GROQ_WHISPER_MODEL,
                language=language,
                response_format="json",
            )
        Path(tmp_path).unlink(missing_ok=True)
        text = getattr(transcription, "text", "") or ""
        detected_lang = getattr(transcription, "language", None) or language
        return {
            "text": text,
            "language": detected_lang,
            "duration_seconds": None,
        }
    except Exception as exc:
        logger.exception("Transcription failed: %s", exc)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Transcription error: {exc}")
