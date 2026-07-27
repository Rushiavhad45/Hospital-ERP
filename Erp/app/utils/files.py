"""Patient-document storage.

Files never land inside the web root: they live under ``UPLOAD_DIR`` and are
served only through an authorised API endpoint. Names are randomized so the
original filename can never be used for traversal or scripting tricks.
"""
from __future__ import annotations

import secrets
from pathlib import Path

from fastapi import UploadFile

from app.core.config import get_settings
from app.exceptions import BusinessRuleError

settings = get_settings()

ALLOWED = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
}


def upload_root() -> Path:
    root = Path(settings.UPLOAD_DIR).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


async def save_patient_document(patient_id: int, upload: UploadFile) -> tuple[str, str, int]:
    """Persist an upload. Returns (relative_path, content_type, size_bytes)."""
    ext = Path(upload.filename or "").suffix.lower()
    if ext not in ALLOWED:
        raise BusinessRuleError(
            "Unsupported file type. Allowed: PNG, JPG, WEBP, PDF.",
            details={"allowed": sorted(ALLOWED)},
        )
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    data = await upload.read()
    if len(data) == 0:
        raise BusinessRuleError("The uploaded file is empty.")
    if len(data) > max_bytes:
        raise BusinessRuleError(f"File too large — limit is {settings.MAX_UPLOAD_MB} MB.")

    rel = Path(f"patient_{patient_id}") / f"{secrets.token_hex(16)}{ext}"
    dest = upload_root() / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return rel.as_posix(), ALLOWED[ext], len(data)


def resolve_stored(rel_path: str) -> Path:
    """Resolve a stored relative path, refusing anything outside UPLOAD_DIR."""
    root = upload_root()
    p = (root / rel_path).resolve()
    if root not in p.parents and p != root:
        raise BusinessRuleError("Invalid file path.")
    if not p.is_file():
        raise BusinessRuleError("File is missing from storage.")
    return p
