"""Document listing, details, and page-image retrieval endpoints."""

from __future__ import annotations

from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_storage
from app.models.database import DocumentORM, PageORM
from app.models.schemas import (
    DocumentDetail, DocumentSummary, ProcessingStatus,
)
from app.security.api_auth import verify_api_key
from app.services.storage import StorageService
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api", tags=["documents"])


# ============================================================
# List all documents
# ============================================================
@router.get("/documents", response_model=List[DocumentSummary],
            summary="List all uploaded documents")
async def list_documents(
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    rows = db.query(DocumentORM).order_by(DocumentORM.created_at.desc()).all()
    return [
        DocumentSummary(
            document_id=d.id,
            filename=d.filename,
            document_type=d.document_type,
            topic=d.topic,
            sensitivity_level=d.sensitivity_level,
            page_count=d.page_count,
            status=ProcessingStatus(d.status),
            uploaded_at=d.created_at,
        )
        for d in rows
    ]


# ============================================================
# Document details
# ============================================================
@router.get("/documents/{document_id}", response_model=DocumentDetail,
            summary="Get full document details")
async def get_document(
    document_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    doc = db.get(DocumentORM, document_id)
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")

    return DocumentDetail(
        document_id=doc.id,
        filename=doc.filename,
        document_type=doc.document_type,
        topic=doc.topic,
        sensitivity_level=doc.sensitivity_level,
        page_count=doc.page_count,
        status=ProcessingStatus(doc.status),
        uploaded_at=doc.created_at,
        classification=None,
        language=doc.language,
        full_text=doc.full_text,
        page_images=[p.image_url or p.image_path
                     for p in doc.pages if p.image_url or p.image_path],
        metadata=doc.extra_metadata or {},
    )


# ============================================================
# Page thumbnail
# ============================================================
@router.get("/documents/{document_id}/page/{page_number}/thumbnail",
            summary="Get a low-res thumbnail of a page")
async def get_page_thumbnail(
    document_id: str,
    page_number: int,
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage),
    _: str = Depends(verify_api_key),
):
    path = storage.get_page_image_path(document_id, page_number)
    if not path:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Page not found")
    return FileResponse(path, media_type="image/png")


# ============================================================
# Full page image
# ============================================================
@router.get("/documents/{document_id}/page/{page_number}/full",
            summary="Get the full-resolution page image")
async def get_page_full(
    document_id: str,
    page_number: int,
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage),
    _: str = Depends(verify_api_key),
):
    path = storage.get_page_image_path(document_id, page_number)
    if not path:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Page not found")
    return FileResponse(path, media_type="image/png")
