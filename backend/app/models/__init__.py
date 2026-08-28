"""SQLAlchemy models. Importing this package registers every table on
``Base.metadata`` (used by Alembic autogenerate)."""

from __future__ import annotations

from app.models.audit import AuditLog
from app.models.base import Base
from app.models.document import Document
from app.models.enums import DocumentStatus, SourceFormat
from app.models.matter import Matter
from app.models.tenant import Tenant

__all__ = [
    "AuditLog",
    "Base",
    "Document",
    "DocumentStatus",
    "Matter",
    "SourceFormat",
    "Tenant",
]
