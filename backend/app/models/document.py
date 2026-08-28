"""Document — one uploaded file moving through the pipeline."""

from __future__ import annotations

import uuid

from sqlalchemy import (
    BigInteger,
    Boolean,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.enums import DocumentStatus, SourceFormat


class Document(Base, TimestampMixin):
    __tablename__ = "documents"
    __table_args__ = (
        # Exact-content dedup, scoped per tenant.
        UniqueConstraint("tenant_id", "content_sha256", name="uq_documents_tenant_sha256"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    matter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("matters.id", ondelete="CASCADE"), index=True, nullable=False
    )

    original_filename: Mapped[str] = mapped_column(String(1024), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    source_format: Mapped[SourceFormat] = mapped_column(
        Enum(SourceFormat, name="source_format", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)

    # Set by ingestion for PDFs; null otherwise / until known.
    is_scanned: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    status: Mapped[DocumentStatus] = mapped_column(
        Enum(
            DocumentStatus, name="document_status", values_callable=lambda e: [m.value for m in e]
        ),
        default=DocumentStatus.QUEUED,
        server_default=DocumentStatus.QUEUED.value,
        index=True,
        nullable=False,
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
