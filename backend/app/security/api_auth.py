"""
API key authentication and rate limiting.

A simple X-API-Key header guard. In production, this should be replaced
with a real auth provider (e.g., Auth0, Clerk, Supabase Auth). The
rate limiter uses `slowapi` and stores counts in memory (good for MVP).
"""

from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


# ============================================================
# Rate Limiter
# ============================================================
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{settings.RATE_LIMIT_PER_MINUTE}/minute"],
    storage_uri="memory://",
)


# ============================================================
# API Key Auth
# ============================================================
async def verify_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> str:
    """
    FastAPI dependency that enforces a static API key.

    Returns the validated key (or raises 401). If the env var is unset
    or the placeholder, the endpoint is treated as public (dev mode).
    """
    # Dev bypass: if the configured key is still the placeholder, skip auth
    placeholder_keys = {"", "change-me-to-a-long-random-string", "your-api-key"}
    if settings.API_KEY in placeholder_keys and settings.APP_ENV == "development":
        logger.warning("API key auth disabled (development mode, placeholder key)")
        return "dev-bypass"

    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    if x_api_key != settings.API_KEY:
        logger.warning("Invalid API key attempt from key ending in ...%s", x_api_key[-4:])
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )
    return x_api_key


def get_rate_limiter() -> Limiter:
    """Return the shared rate-limiter instance (used by main.py)."""
    return limiter
