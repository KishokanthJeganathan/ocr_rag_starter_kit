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
    FAILED = "failed"
