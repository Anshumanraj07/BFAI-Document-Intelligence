"""
SQLAlchemy ORM models for the BFAI backend.

We use the synchronous SQLAlchemy 2.0 style. FastAPI runs sync
DB operations in a threadpool automatically, which is sufficient
for an MVP. Swap to `AsyncSession` later if needed.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from typing import Generator

from sqlalchemy import (
    Column, DateTime, Integer, String, Text, Enum as SAEnum, ForeignKey, JSON
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


# ============================================================
# Base & Engine
# ============================================================
class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Convert async URL to sync for SQLAlchemy core (we keep async via aiosqlite
# only as the DSN string; for simplicity, run sync engine in threadpool).
_sync_url = settings.DATABASE_URL.replace("+aiosqlite", "")
engine = create_engine(_sync_url, echo=False, future=True, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


# ============================================================
# Models
# ============================================================
class JobORM(Base):
    """A processing job (one per upload or bulk-upload)."""
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    total_files: Mapped[int] = mapped_column(Integer, default=0)
    completed_files: Mapped[int] = mapped_column(Integer, default=0)
    current_file: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    documents: Mapped[list["DocumentORM"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class DocumentORM(Base):
    """An uploaded document and its metadata."""
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id"), index=True)
    filename: Mapped[str] = mapped_column(String(512))
    storage_path: Mapped[str] = mapped_column(String(1024))
    mime_type: Mapped[str] = mapped_column(String(128))
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    file_hash: Mapped[str] = mapped_column(String(64), default="", index=True)


    # Parsing
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Classification
    document_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    topic: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sensitivity_level: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_sensitive: Mapped[bool] = mapped_column(default=False)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    classification_confidence: Mapped[float | None] = mapped_column(nullable=True)

    # Status & metadata
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_metadata: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    job: Mapped[JobORM] = relationship(back_populates="documents")
    pages: Mapped[list["PageORM"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class PageORM(Base):
    """A rendered page of a document (image + extracted text)."""
    __tablename__ = "pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id"), index=True)
    page_number: Mapped[int] = mapped_column(Integer)
    image_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    has_handwriting: Mapped[bool] = mapped_column(default=False)
    has_tables: Mapped[bool] = mapped_column(default=False)
    table_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    document: Mapped[DocumentORM] = relationship(back_populates="pages")


class ChatSessionORM(Base):
    """Multi-turn chat session."""
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    document_filter: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    messages: Mapped[list["ChatMessageORM"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="ChatMessageORM.created_at"
    )


class ChatMessageORM(Base):
    """A single message in a chat session."""
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("chat_sessions.id"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    citations: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    session: Mapped[ChatSessionORM] = relationship(back_populates="messages")


# ============================================================
# Session & Initialization
# ============================================================
def init_db() -> None:
    """Create all tables. Idempotent — safe to call on startup."""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialized at %s", settings.DATABASE_URL)
    except Exception as exc:  # pragma: no cover
        logger.exception("Failed to initialize database: %s", exc)
        raise


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Context-managed DB session with auto-commit/rollback."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
