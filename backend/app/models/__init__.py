"""SQLAlchemy models. Importing this package registers every table on
``Base.metadata`` (used by Alembic autogenerate)."""

from __future__ import annotations

from app.models.base import Base
from app.models.document import Document
from app.models.enums import DocumentStatus, DocumentType, SourceFormat
from app.models.extraction import DocumentExtraction
from app.models.layout import DocumentLayout
from app.models.matter import Matter
from app.models.tenant import Tenant

__all__ = [
    "Base",
    "Document",
    "DocumentExtraction",
    "DocumentLayout",
    "DocumentStatus",
    "DocumentType",
    "Matter",
    "SourceFormat",
    "Tenant",
]
