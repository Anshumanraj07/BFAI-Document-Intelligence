"""
Application configuration.

Loads all environment variables via Pydantic Settings, validates them
at startup, and exposes a single `settings` instance throughout the app.
"""

from __future__ import annotations

from functools import lru_cache
from typing import List, Literal, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---------- Application ----------
    APP_NAME: str = "BFAI Document Intelligence"
    APP_ENV: Literal["development", "staging", "production"] = "development"
    APP_VERSION: str = "1.0.0"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    APP_DEBUG: bool = True
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # ---------- Security ----------
    CORS_ORIGINS: str = "http://localhost:3000"
    API_KEY: str = "change-me-to-a-long-random-string"
    MAX_FILE_SIZE_BYTES: int = 10 * 1024 * 1024        # 10 MB
    MAX_BULK_SIZE_BYTES: int = 50 * 1024 * 1024        # 50 MB
    MAX_PAGES_PER_DOC: int = 5
    RATE_LIMIT_PER_MINUTE: int = 60

    # ---------- Database ----------
    DATABASE_URL: str = "sqlite+aiosqlite:///./bfai.db"

    # ---------- Vector Database (Qdrant) ----------
    QDRANT_URL: str = "https://your-cluster.qdrant.io"
    QDRANT_API_KEY: str = "your-qdrant-api-key"
    QDRANT_COLLECTION_NAME: str = "bfai_documents"
    QDRANT_VECTOR_SIZE: int = 768

   # ---------- LLM Providers ----------
    GROQ_API_KEY: str = "your-groq-api-key"
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_WHISPER_MODEL: str = "whisper-large-v3"

    GEMINI_API_KEY: str = "your-gemini-api-key"
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-001"

    # ---------- Storage ----------
    CLOUDINARY_CLOUD_NAME: Optional[str] = None
    CLOUDINARY_API_KEY: Optional[str] = None
    CLOUDINARY_API_SECRET: Optional[str] = None
    LOCAL_STORAGE_PATH: str = "./storage"

    # ---------- Validators ----------
    @field_validator("CORS_ORIGINS")
    @classmethod
    def _strip_cors(cls, v: str) -> str:
        return v.strip()

    @field_validator("MAX_FILE_SIZE_BYTES", "MAX_BULK_SIZE_BYTES")
    @classmethod
    def _validate_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Size limit must be positive")
        return v

    # ---------- Derived helpers ----------
    @property
    def cors_origin_list(self) -> List[str]:
        """Parse the comma-separated CORS_ORIGINS string into a list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def has_cloudinary(self) -> bool:
        return all([self.CLOUDINARY_CLOUD_NAME, self.CLOUDINARY_API_KEY, self.CLOUDINARY_API_SECRET])


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor (singleton)."""
    return Settings()


# Global singleton
settings = get_settings()

