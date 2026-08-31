"""Pydantic models for the HTTP API (request bodies and responses).

These are the API contract — separate from the SQLAlchemy models, which are the
database contract.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

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


class AskRequest(BaseModel):
    question: str
    document_id: uuid.UUID | None = None  # set = ask one document; unset = whole corpus


class SourceOut(BaseModel):
    n: int
    document_id: str
    filename: str
    page: int
    distance: float
    text: str


class AskResponse(BaseModel):
    answer: str
    sources: list[SourceOut]


class SyntheticNdaRequest(BaseModel):
    """Parameters for POST /v1/documents/synthetic. Any field left unset is
    filled from a random seed, so each generated PDF is still unique."""

    matter_id: uuid.UUID
    disclosing_party: str | None = None
    receiving_party: str | None = None
    effective_date: dt.date | None = None
    term_years: int | None = None
    agreement_type: Literal["one-way", "mutual"] | None = None
    governing_law: str | None = None
    # Deliberately break the document: "date_order", "missing_party_sig",
    # "missing_governing_law".
    violations: list[str] = Field(default_factory=list)
