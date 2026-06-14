"""
Document listing and page image retrieval endpoints.
"""

from __future__ import annotations

from typing import List, Optional
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["documents"])


class DocumentSummary(BaseModel):
    document_id: str
    filename: str
    document_type: Optional[str] = None
    topic: Optional[str] = None
    sensitivity_level: Optional[str] = None
    page_count: int
    status: str
    uploaded_at: str


class ProcessingStatus(BaseModel):
    QUEUED = "queued"
    PARSING = "parsing"
    CLASSIFYING = "classifying"
    INDEXED = "indexed"
    FAILED = "failed"


# Mock documents database
documents_db = [
    {
        "document_id": "doc-001",
        "filename": "sample_document.pdf",
        "document_type": "PDF",
        "topic": "Technical",
        "sensitivity_level": "Normal",
        "page_count": 10,
        "status": "indexed",
        "uploaded_at": "2024-01-15T10:30:00Z",
    }
]


@router.get("/documents", response_model=List[DocumentSummary], summary="List all uploaded documents")
async def list_documents() -> List[dict]:
    return documents_db


@router.get("/documents/{document_id}", summary="Get full document details")
async def get_document(document_id: str) -> dict:
    for doc in documents_db:
        if doc["document_id"] == document_id:
            return doc
    raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")


@router.get("/documents/{document_id}/page/{page_number}/thumbnail", summary="Get a low-res thumbnail of a page")
async def get_page_thumbnail(document_id: str, page_number: int):
    """
    Returns a thumbnail image for the specified page.
    In production, this would return actual generated thumbnails.
    """
    # Check if document exists
    doc_exists = any(doc["document_id"] == document_id for doc in documents_db)
    if not doc_exists:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")

    # Return placeholder image for now
    # In production, return: FileResponse(storage.get_page_image_path(document_id, page_number))
    placeholder_svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="100" height="140" viewBox="0 0 100 140">
        <rect fill="#f3f4f6" width="100" height="140" rx="4"/>
        <text x="50" y="50" text-anchor="middle" fill="#6b7280" font-size="12">{document_id[:8]}</text>
        <text x="50" y="75" text-anchor="middle" fill="#9ca3af" font-size="10">Page {page_number}</text>
    </svg>'''

    from fastapi.responses import Response
    return Response(content=placeholder_svg, media_type="image/svg+xml")


@router.get("/documents/{document_id}/page/{page_number}/full", summary="Get the full-resolution page image")
async def get_page_full(document_id: str, page_number: int):
    """
    Returns a full-resolution image for the specified page.
    In production, this would return actual page images.
    """
    # Check if document exists
    doc_exists = any(doc["document_id"] == document_id for doc in documents_db)
    if not doc_exists:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")

    # Return placeholder image for now
    placeholder_svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="600" height="850" viewBox="0 0 600 850">
        <rect fill="#ffffff" width="600" height="850" rx="4" stroke="#e5e7eb" stroke-width="2"/>
        <text x="300" y="100" text-anchor="middle" fill="#374151" font-size="18" font-weight="bold">{document_id[:12]}</text>
        <text x="300" y="130" text-anchor="middle" fill="#6b7280" font-size="14">Page {page_number}</text>
        <rect x="50" y="160" width="500" height="600" fill="#f9fafb" rx="2"/>
        <text x="300" y="200" text-anchor="middle" fill="#9ca3af" font-size="12">Document content preview</text>
        <text x="300" y="230" text-anchor="middle" fill="#9ca3af" font-size="12">Full page would render here</text>
    </svg>'''

    from fastapi.responses import Response
    return Response(content=placeholder_svg, media_type="image/svg+xml")
