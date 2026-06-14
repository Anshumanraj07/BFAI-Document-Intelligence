"""
Upload endpoints: single + bulk.

Files are validated, saved to storage, and a background task is queued
to run the full processing pipeline (parse → classify → index).
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import (
    APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status,
)
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_pipeline, get_storage
from app.models.database import DocumentORM, JobORM
from app.models.schemas import (
    BulkUploadResponse, JobStatusResponse, ProcessingStatus, UploadResponse,
)
from app.security.api_auth import verify_api_key
from app.security.file_validation import FileValidationError, validate_upload
from app.services.processing import ProcessingPipeline
from app.services.storage import StorageService
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api", tags=["upload"])


# ============================================================
# Single file upload
# ============================================================
@router.post("/upload", response_model=UploadResponse,
             summary="Upload a single document")
async def upload_single(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="PDF, PNG, JPG, or TXT file"),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage),
    pipeline: ProcessingPipeline = Depends(get_pipeline),
    _: str = Depends(verify_api_key),
) -> UploadResponse:
    """Upload a single file and start async processing."""
    if not file.filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Missing filename")

    # Read content
    content = await file.read()

    # Validate
    try:
        validate_upload(filename=file.filename, content=content, mime_type=file.content_type)
    except FileValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail={
            "code": exc.code, "message": exc.message
        })

    # Persist job + document
    job_id = str(uuid.uuid4())
    document_id = str(uuid.uuid4())
    safe_path = await storage.save_upload(original_filename=file.filename, content=content)

    job = JobORM(id=job_id, status=ProcessingStatus.QUEUED.value, total_files=1, completed_files=0)
    doc = DocumentORM(
        id=document_id,
        job_id=job_id,
        filename=file.filename,
        storage_path=str(safe_path),
        mime_type=file.content_type or "application/octet-stream",
        file_size=len(content),
        status=ProcessingStatus.QUEUED.value,
    )
    db.add(job)
    db.add(doc)
    db.commit()

    # Schedule background processing
    background_tasks.add_task(
        pipeline.process_document,
        job_id=job_id,
        document_id=document_id,
        file_path=str(safe_path),
        original_filename=file.filename,
    )

    return UploadResponse(
        job_id=job_id,
        document_id=document_id,
        filename=file.filename,
        status=ProcessingStatus.QUEUED,
        message="File accepted and queued for processing",
    )


# ============================================================
# Bulk upload
# ============================================================
@router.post("/upload-bulk", response_model=BulkUploadResponse,
             summary="Upload multiple documents at once")
async def upload_bulk(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(..., description="Multiple files"),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage),
    pipeline: ProcessingPipeline = Depends(get_pipeline),
    _: str = Depends(verify_api_key),
) -> BulkUploadResponse:
    """Upload multiple files. Each is processed independently in the background."""
    if not files:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No files provided")
    if len(files) > 20:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Maximum 20 files per bulk upload")

    job_id = str(uuid.uuid4())
    accepted: List[str] = []
    doc_ids: List[str] = []
    saved_paths: List[str] = []

    contents: List[tuple[UploadFile, bytes]] = []
    for f in files:
        if not f.filename:
            continue
        try:
            content = await f.read()
            validate_upload(filename=f.filename, content=content,
                            mime_type=f.content_type, bulk=True)
            contents.append((f, content))
        except FileValidationError as exc:
            logger.warning("Skipping invalid file %s: %s", f.filename, exc.message)

    if not contents:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "All files failed validation")

    job = JobORM(id=job_id, status=ProcessingStatus.QUEUED.value,
                 total_files=len(contents), completed_files=0)
    db.add(job)
    db.flush()

    for f, content in contents:
        document_id = str(uuid.uuid4())
        safe_path = await storage.save_upload(original_filename=f.filename, content=content)
        doc = DocumentORM(
            id=document_id,
            job_id=job_id,
            filename=f.filename,
            storage_path=str(safe_path),
            mime_type=f.content_type or "application/octet-stream",
            file_size=len(content),
            status=ProcessingStatus.QUEUED.value,
        )
        db.add(doc)
        accepted.append(f.filename)
        doc_ids.append(document_id)
        saved_paths.append(str(safe_path))
    db.commit()

    for doc_id, file_path, fname in zip(doc_ids, saved_paths, accepted):
        background_tasks.add_task(
            pipeline.process_document,
            job_id=job_id,
            document_id=doc_id,
            file_path=file_path,
            original_filename=fname,
        )

    return BulkUploadResponse(
        job_id=job_id,
        files_accepted=accepted,
        document_ids=doc_ids,
        total_files=len(accepted),
        status=ProcessingStatus.QUEUED,
    )


# ============================================================
# Job status
# ============================================================
@router.get("/upload/{job_id}/status", response_model=JobStatusResponse,
            summary="Get processing status of a job")
async def get_job_status(
    job_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
) -> JobStatusResponse:
    job = db.get(JobORM, job_id)
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")

    current = next(
        (d.filename for d in job.documents
         if d.status not in (ProcessingStatus.INDEXED.value, ProcessingStatus.FAILED.value)),
        None,
    )
    return JobStatusResponse(
        job_id=job.id,
        status=ProcessingStatus(job.status),
        completed_files=job.completed_files,
        total_files=job.total_files,
        current_file=current,
        error=job.error,
        started_at=job.started_at,
        updated_at=job.updated_at,
    )
