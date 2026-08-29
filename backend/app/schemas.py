"""Pydantic models for the HTTP API (request bodies and responses).

These are the API contract — separate from the SQLAlchemy models, which are the
database contract.
"""

from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict

from app.models.enums import DocumentStatus, DocumentType, SourceFormat


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    matter_id: uuid.UUID
    original_filename: str
    mime_type: str
    source_format: SourceFormat
    byte_size: int
    content_sha256: str
    is_scanned: bool | None
    page_count: int | None
    status: DocumentStatus
    doc_type: DocumentType | None
    doc_type_confidence: float | None
    error: str | None
    created_at: dt.datetime


class UploadResult(BaseModel):
    document: DocumentOut
    duplicate: bool
