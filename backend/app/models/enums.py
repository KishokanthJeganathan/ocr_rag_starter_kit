"""Enumerations stored as native PostgreSQL enum types."""

from __future__ import annotations

import enum


class SourceFormat(enum.StrEnum):
    """The kind of file that was uploaded, decided from its content."""

    PDF = "pdf"
    PNG = "png"
    JPG = "jpg"
    DOCX = "docx"


class DocumentStatus(enum.StrEnum):
    """Where a document is in the pipeline. Later stages add values
    (``needs_review``, ``approved``, ...) via ``ALTER TYPE``.
    """

    QUEUED = "queued"
    PROCESSING = "processing"
    PROCESSED = "processed"  # OCR + classification finished
    FAILED = "failed"


class DocumentType(enum.StrEnum):
    """What kind of document this is, decided by the classifier after OCR.
    ``None`` on the row means not classified yet (or the classifier abstained).
    """

    NDA = "nda"
    INVOICE = "invoice"
    OTHER = "other"
