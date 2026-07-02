"""File upload routes."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from src.api.middleware.auth import get_current_user
from src.config import PROJECT_ROOT

router = APIRouter(prefix="/api/v1", tags=["uploads"])

PDF_SUFFIXES = {".pdf"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}
UPLOAD_ROOT = PROJECT_ROOT / "data" / "uploads"


def _sanitize_filename(filename: str) -> str:
    cleaned = Path(filename or "uploaded_file").name.strip()
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", cleaned)
    return cleaned or "uploaded_file"


def resolve_upload_target(filename: str) -> tuple[str, Path]:
    safe_name = _sanitize_filename(filename)
    suffix = Path(safe_name).suffix.lower()

    if suffix in PDF_SUFFIXES:
        file_type = "pdf"
        target_dir = UPLOAD_ROOT / "pdf"
    elif suffix in IMAGE_SUFFIXES:
        file_type = "image"
        target_dir = UPLOAD_ROOT / "images"
    else:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Only pdf, png, jpg, and jpeg are allowed.",
        )

    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / safe_name

    if target_path.exists():
        stem = target_path.stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target_path = target_dir / f"{stem}_{timestamp}{target_path.suffix.lower()}"

    return file_type, target_path


@router.post("/uploads")
async def upload_file(req: Request, file: UploadFile = File(...)):
    await get_current_user(req)

    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required.")

    file_type, target_path = resolve_upload_target(file.filename)

    try:
        contents = await file.read()
        if not contents:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")
        target_path.write_bytes(contents)
    finally:
        await file.close()

    relative_path = target_path.relative_to(PROJECT_ROOT)
    return {
        "success": True,
        "filename": target_path.name,
        "file_type": file_type,
        "relative_path": relative_path.as_posix(),
        "size": target_path.stat().st_size,
    }
