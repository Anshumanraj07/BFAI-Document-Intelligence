"""
Background processing pipeline.

Triggered by upload endpoints via FastAPI's BackgroundTasks. Orchestrates:
  parse  →  classify  →  chunk + embed  →  persist  →  store vectors
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.classifiers.document_classifier import DocumentClassifier
from app.classifiers.schema import ClassificationOutput
from app.config import settings
from app.models.database import (
    DocumentORM, JobORM, PageORM, get_session,
)
from app.models.schemas import ProcessingStatus
from app.parsers import (
    ImageParser, PDFParser, TableParser, HandwrittenParser, BaseParser,
)
from app.rag.vector_store import VectorStore
from app.security.pii_filter import redact_text
from app.services.embedding import EmbeddingService
from app.services.storage import StorageService
from app.utils.helpers import chunk_text, compute_file_hash, utc_now
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ProcessingError(Exception):
    pass


class ProcessingPipeline:
    """End-to-end async processing for a single document."""

    def __init__(
        self,
        *,
        vector_store: VectorStore,
        embedding_service: EmbeddingService,
        storage: StorageService,
        classifier: DocumentClassifier,
    ) -> None:
        self.vector_store = vector_store
        self.embeddings = embedding_service
        self.storage = storage
        self.classifier = classifier
        self.pdf_parser = PDFParser()
        self.image_parser = ImageParser()
        self.handwritten_parser = HandwrittenParser()
        self.table_parser = TableParser()

    def _select_parser(self, file_path: str) -> BaseParser:
        ext = Path(file_path).suffix.lower()
        if ext == ".pdf":
            return self.pdf_parser
        if ext in {".png", ".jpg", ".jpeg"}:
            return self.image_parser
        return self.image_parser  # default fallback

    # ============================================================
    # Main entry point
    # ============================================================
    async def process_document(
        self,
        *,
        job_id: str,
        document_id: str,
        file_path: str,
        original_filename: str,
    ) -> None:
        """
        Process one document end-to-end. Updates the DB and vector store
        as it goes. Errors are logged and stored, not raised.
        """
        logger.info("Processing %s (doc=%s, job=%s)", original_filename, document_id, job_id)
        path = Path(file_path)
        try:
            # ---- 1. Update status: parsing ----
            self._update_document_status(document_id, ProcessingStatus.PARSING.value)

            # ---- 2. Parse ----
            parser = self._select_parser(file_path)
            parsed = await parser.parse(file_path)
            if not parsed.is_successful:
                raise ProcessingError(f"Parsing failed: {parsed.error}")

            # ---- 3. Redact PII from text before storage/embedding ----
            redacted_text = redact_text(parsed.full_text)

            # ---- 4. Update status + persist pages ----
            self._update_document_status(document_id, ProcessingStatus.PARSED.value)
            self._persist_pages(document_id, parsed)

            # ---- 5. Classify ----
            self._update_document_status(document_id, ProcessingStatus.CLASSIFYING.value)
            classification: Optional[ClassificationOutput] = None
            try:
                classification = await self.classifier.classify(redacted_text)
            except Exception as exc:
                logger.warning("Classification failed (non-fatal): %s", exc)
                classification = None

            # ---- 6. Persist classification + text ----
            self._persist_classification(document_id, redacted_text, classification)

            # ---- 7. Chunk + embed + index ----
            self._update_document_status(document_id, ProcessingStatus.INDEXING.value)
            chunk_count = await self._index_document(
                document_id=document_id,
                filename=original_filename,
                text=redacted_text,
                classification=classification,
            )

            # ---- 8. Mark complete ----
            self._update_document_status(
                document_id, ProcessingStatus.INDEXED.value, extra={"chunks_indexed": chunk_count}
            )
            self._increment_job_progress(job_id)
            logger.info("Done: %s (chunks=%d, type=%s)",
                        original_filename, chunk_count,
                        classification.document_type if classification else "unknown")

        except Exception as exc:
            logger.exception("Processing failed for %s: %s", document_id, exc)
            self._update_document_status(
                document_id, ProcessingStatus.FAILED.value, error=str(exc)
            )
            self._increment_job_progress(job_id)
            raise

    # ============================================================
    # Vector indexing
    # ============================================================
    async def _index_document(
        self,
        *,
        document_id: str,
        filename: str,
        text: str,
        classification: Optional[ClassificationOutput],
    ) -> int:
        """Chunk the text, embed each chunk, and upsert to the vector store."""
        chunks = chunk_text(text, chunk_size=800, chunk_overlap=100)
        if not chunks:
            return 0

        embeddings = await self.embeddings.embed_texts(chunks)
        if len(embeddings) != len(chunks):
            logger.warning("Embedding count mismatch: %d vs %d", len(embeddings), len(chunks))
            return 0

        topic = classification.topic if classification else None
        sensitivity = classification.sensitivity_level.value if classification else "Low"

        inserted = 0
        for idx, (chunk, vec) in enumerate(zip(chunks, embeddings)):
            await self.vector_store.insert_chunk(
                text=chunk,
                embedding=vec,
                document_id=document_id,
                document_name=filename,
                page_number=1,  # page-level granularity could be added later
                topic=topic,
                sensitivity_level=sensitivity,
            )
            inserted += 1
        return inserted

    # ============================================================
    # DB helpers
    # ============================================================
    def _update_document_status(
        self,
        document_id: str,
        status: str,
        *,
        error: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        with get_session() as db:
            doc = db.get(DocumentORM, document_id)
            if not doc:
                return
            doc.status = status
            doc.updated_at = utc_now().replace(tzinfo=None)
            if error:
                doc.error = error
            if extra and doc.extra_metadata:
                doc.extra_metadata.update(extra)

    def _persist_pages(self, document_id: str, parsed) -> None:
        with get_session() as db:
            for p in parsed.pages:
                page_orm = PageORM(
                    document_id=document_id,
                    page_number=p.page_number,
                    image_path=p.image_path,
                    image_url=p.image_url,
                    text=p.text,
                    has_handwriting=p.has_handwriting,
                    has_tables=p.has_tables,
                    table_data={"tables": p.tables} if p.tables else None,
                )
                db.add(page_orm)
            # Update page count
            doc = db.get(DocumentORM, document_id)
            if doc:
                doc.page_count = parsed.page_count
                doc.full_text = parsed.full_text
                doc.file_hash = compute_file_hash(
                    Path(parsed.file_path).read_bytes()
                ) if Path(parsed.file_path).exists() else doc.file_hash

    def _persist_classification(
        self,
        document_id: str,
        text: str,
        classification: Optional[ClassificationOutput],
    ) -> None:
        with get_session() as db:
            doc = db.get(DocumentORM, document_id)
            if not doc:
                return
            if classification:
                doc.document_type = classification.document_type.value
                doc.topic = classification.topic
                doc.sensitivity_level = classification.sensitivity_level.value
                doc.is_sensitive = classification.is_sensitive
                doc.language = classification.language
                doc.classification_confidence = classification.confidence
            doc.full_text = text
            doc.status = ProcessingStatus.CLASSIFIED.value

    def _increment_job_progress(self, job_id: str) -> None:
        with get_session() as db:
            job = db.get(JobORM, job_id)
            if not job:
                return
            job.completed_files += 1
            job.updated_at = utc_now().replace(tzinfo=None)
            if job.completed_files >= job.total_files:
                # Mark job complete only if no failures
                failed = any(d.status == ProcessingStatus.FAILED.value
                             for d in job.documents)
                job.status = (ProcessingStatus.FAILED.value if failed
                              else ProcessingStatus.INDEXED.value)
