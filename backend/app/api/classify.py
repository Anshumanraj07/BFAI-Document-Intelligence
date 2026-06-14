"""Classification endpoint: re-classify an already-uploaded document."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_classifier, get_db
from app.classifiers.document_classifier import DocumentClassifier
from app.classifiers.schema import ClassificationOutput
from app.models.database import DocumentORM
from app.models.schemas import ClassificationRequest
from app.security.api_auth import verify_api_key
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api", tags=["classify"])


@router.post("/classify", response_model=ClassificationOutput,
             summary="Re-classify a document by ID")
async def classify_document(
    request: ClassificationRequest,
    db: Session = Depends(get_db),
    classifier: DocumentClassifier = Depends(get_classifier),
    _: str = Depends(verify_api_key),
) -> ClassificationOutput:
    doc = db.get(DocumentORM, request.document_id)
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    if not doc.full_text:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Document has no parsed text; upload may still be processing",
        )
    try:
        result = await classifier.classify(doc.full_text)
    except Exception as exc:
        logger.exception("Classification failed: %s", exc)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"Classifier error: {exc}",
        )

    # Persist updated classification
    doc.document_type = result.document_type.value
    doc.topic = result.topic
    doc.sensitivity_level = result.sensitivity_level.value
    doc.is_sensitive = result.is_sensitive
    doc.language = result.language
    doc.classification_confidence = result.confidence
    db.commit()
    return result
