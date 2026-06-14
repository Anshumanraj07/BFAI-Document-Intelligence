"""
Pydantic v2 schemas for all API request/response payloads.

All public-facing data structures are defined here for type-safety,
auto-validation, and Swagger documentation.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ============================================================
# Enumerations
# ============================================================
class DocumentType(str, Enum):
    """Supported document types for classification."""
    INVOICE = "invoice"
    REPORT = "report"
    CONTRACT = "contract"
    RESUME = "resume"
    RECEIPT = "receipt"
    OTHER = "other"


class ProcessingStatus(str, Enum):
    """Lifecycle states of an upload/processing job."""
    QUEUED = "queued"
    PARSING = "parsing"
    PARSED = "parsed"
    CLASSIFYING = "classifying"
    CLASSIFIED = "classified"
    INDEXING = "indexing"
    INDEXED = "indexed"
    FAILED = "failed"


class SensitivityLevel(str, Enum):
    """How sensitive the document content is."""
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


# ============================================================
# Base configuration
# ============================================================
class APIModel(BaseModel):
    """Base model with common configuration."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        use_enum_values=True,
        populate_by_name=True,
    )


# ============================================================
# Upload Schemas
# ============================================================
class UploadResponse(APIModel):
    """Response returned after a successful single file upload."""
    job_id: str = Field(..., description="Unique job identifier for tracking")
    document_id: str = Field(..., description="Unique document identifier")
    filename: str
    status: ProcessingStatus
    message: str = "File accepted and queued for processing"


class BulkUploadResponse(APIModel):
    """Response after a bulk upload."""
    job_id: str
    files_accepted: List[str]
    document_ids: List[str]
    total_files: int
    status: ProcessingStatus


class JobStatusResponse(APIModel):
    """Status of a processing job (polled by the frontend)."""
    job_id: str
    status: ProcessingStatus
    completed_files: int
    total_files: int
    current_file: Optional[str] = None
    error: Optional[str] = None
    started_at: datetime
    updated_at: datetime


# ============================================================
# Classification Schemas
# ============================================================
class ClassificationRequest(APIModel):
    """Request body to trigger (or re-trigger) classification."""
    document_id: str


class ClassificationResult(APIModel):
    """Structured classification output (matches `classifiers/schema.py`)."""
    document_type: DocumentType
    topic: str
    is_sensitive: bool
    sensitivity_level: SensitivityLevel
    language: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    raw: Optional[Dict[str, Any]] = None


# ============================================================
# Document Schemas
# ============================================================
class DocumentSummary(APIModel):
    """Lightweight document info for list endpoints."""
    document_id: str
    filename: str
    document_type: Optional[DocumentType] = None
    topic: Optional[str] = None
    sensitivity_level: Optional[SensitivityLevel] = None
    page_count: int = 0
    status: ProcessingStatus
    uploaded_at: datetime


class DocumentDetail(DocumentSummary):
    """Full document details including parsed content."""
    classification: Optional[ClassificationResult] = None
    language: Optional[str] = None
    full_text: Optional[str] = None
    page_images: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ============================================================
# Chat Schemas
# ============================================================
class ChatMessage(APIModel):
    """A single message in a chat session."""
    role: Literal["user", "assistant", "system"]
    content: str
    citations: Optional[List["Citation"]] = None
    created_at: Optional[datetime] = None


class Citation(APIModel):
    """A source citation attached to an assistant message."""
    document_id: str
    document_name: str
    page_number: int
    chunk_text: Optional[str] = None
    thumbnail_url: Optional[str] = None
    score: Optional[float] = None


class ChatRequest(APIModel):
    """User input for the /chat endpoint."""
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = Field(
        None, description="Existing session ID; new one is generated if omitted"
    )
    document_ids: Optional[List[str]] = Field(
        None, description="Restrict retrieval to specific documents (default: all)"
    )
    top_k: int = Field(default=5, ge=1, le=20)
    history: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Chat history for follow-up questions (merged with database history if provided)"
    )


class ChatResponse(APIModel):
    """Response from the /chat endpoint."""
    session_id: str
    answer: str
    citations: List[Citation] = Field(default_factory=list)
    used_documents: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    needs_more_info: bool = False


# ============================================================
# Voice Schemas
# ============================================================
class VoiceTranscribeResponse(APIModel):
    """Response from the /voice/transcribe endpoint."""
    text: str
    language: Optional[str] = None
    duration_seconds: Optional[float] = None


# ============================================================
# Error Schemas
# ============================================================
class ErrorDetail(APIModel):
    """Structured error detail for 4xx/5xx responses."""
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


class ErrorResponse(APIModel):
    """Standard error envelope returned by all error handlers."""
    error: ErrorDetail


# Update forward references
ChatMessage.model_rebuild()
