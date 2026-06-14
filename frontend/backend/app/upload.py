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

router = APIRouter(prefix="/api", tags=["upload"])


# Process status enum
class ProcessingStatus:
    QUEUED = "queued"
    PARSING = "parsing"
    CLASSIFYING = "classifying"
    INDEXED = "indexed"
    FAILED = "failed"


# ============================================================
# Mock implementation for frontend integration
# ============================================================
jobs_db = {}


@router.post("/upload", summary="Upload a single document")
async def upload_single(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="PDF, PNG, JPG, or TXT file"),
) -> dict:
    """Upload a single file and start async processing."""
    if not file.filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Missing filename")

    content = await file.read()

    job_id = str(uuid.uuid4())
    document_id = str(uuid.uuid4())

    # Store job info
    jobs_db[job_id] = {
        "job_id": job_id,
        "status": ProcessingStatus.QUEUED,
        "completed_files": 0,
        "total_files": 1,
        "current_file": file.filename,
    }

    # Simulate background processing
    async def process_file():
        import asyncio
        jobs_db[job_id]["status"] = ProcessingStatus.PARSING
        await asyncio.sleep(2)
        jobs_db[job_id]["status"] = ProcessingStatus.CLASSIFYING
        await asyncio.sleep(2)
        jobs_db[job_id]["status"] = ProcessingStatus.INDEXED
        jobs_db[job_id]["completed_files"] = 1
        jobs_db[job_id]["current_file"] = None

    background_tasks.add_task(process_file)

    return {
        "job_id": job_id,
        "document_id": document_id,
        "filename": file.filename,
        "status": ProcessingStatus.QUEUED,
        "message": "File accepted and queued for processing",
    }


# ============================================================
# Bulk upload
# ============================================================
@router.post("/upload-bulk", summary="Upload multiple documents at once")
async def upload_bulk(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(..., description="Multiple files"),
) -> dict:
    """Upload multiple files. Each is processed independently in the background."""
    if not files:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No files provided")
    if len(files) > 20:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Maximum 20 files per bulk upload")

    job_id = str(uuid.uuid4())
    accepted: List[str] = []
    doc_ids: List[str] = []

    for f in files:
        if not f.filename:
            continue
        # Read content for validation
        await f.read()
        document_id = str(uuid.uuid4())
        accepted.append(f.filename)
        doc_ids.append(document_id)

    if not accepted:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "All files failed validation")

    # Store job info
    jobs_db[job_id] = {
        "job_id": job_id,
        "status": ProcessingStatus.QUEUED,
        "completed_files": 0,
        "total_files": len(accepted),
        "current_file": accepted[0] if accepted else None,
    }

    # Simulate background processing
    async def process_files():
        import asyncio
        for i, filename in enumerate(accepted):
            jobs_db[job_id]["status"] = ProcessingStatus.PARSING
            jobs_db[job_id]["current_file"] = filename
            await asyncio.sleep(1)
            jobs_db[job_id]["status"] = ProcessingStatus.CLASSIFYING
            await asyncio.sleep(1)
            jobs_db[job_id]["completed_files"] = i + 1
        jobs_db[job_id]["status"] = ProcessingStatus.INDEXED
        jobs_db[job_id]["current_file"] = None

    background_tasks.add_task(process_files)

    return {
        "job_id": job_id,
        "files_accepted": accepted,
        "document_ids": doc_ids,
        "total_files": len(accepted),
        "status": ProcessingStatus.QUEUED,
    }


# ============================================================
# Job status
# ============================================================
@router.get("/upload/{job_id}/status", summary="Get processing status of a job")
async def get_job_status(job_id: str) -> dict:
    job = jobs_db.get(job_id)
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")

    return job
