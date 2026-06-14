"""
Shared pytest fixtures.

Provides:
  * An isolated `TestClient` against the FastAPI app
  * Mocked vector store + embedding service (no external calls)
  * A bypass API key for auth-protected endpoints
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient


# Set required env vars BEFORE importing the app
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("API_KEY", "test-key")
os.environ.setdefault("GROQ_API_KEY", "mock-groq")
os.environ.setdefault("GEMINI_API_KEY", "mock-gemini")
os.environ.setdefault("QDRANT_API_KEY", "mock-qdrant")
os.environ.setdefault("QDRANT_URL", "https://mock.qdrant.io")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_bfai.db")


@pytest.fixture(scope="session")
def tmp_storage() -> Iterator[Path]:
    with tempfile.TemporaryDirectory() as d:
        os.environ["LOCAL_STORAGE_PATH"] = d
        yield Path(d)


@pytest.fixture(scope="session")
def client(tmp_storage: Path) -> Iterator[TestClient]:
    # Late import so env vars are set
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers() -> dict:
    return {"X-API-Key": "test-key"}
