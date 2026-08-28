"""The ingestion flow: detect -> hash -> dedup -> validate matter -> store ->
record. Enqueuing the pipeline job happens in the API layer, after commit.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Document, Matter
from app.models.enums import SourceFormat
from app.services import detect, storage

_EXT = {
    SourceFormat.PDF: "pdf",
    SourceFormat.PNG: "png",
    SourceFormat.JPG: "jpg",
    SourceFormat.DOCX: "docx",
}


class IngestError(Exception):
    """Raised for client-fixable problems; carries an HTTP status."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass
class Ingested:
    document: Document
    duplicate: bool


async def ingest_document(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    matter_id: uuid.UUID,
    filename: str,
    data: bytes,
    actor: str,
) -> Ingested:
    fmt = detect.detect_format(data)
    if fmt is None:
        raise IngestError(415, "unsupported file type (need PDF, PNG, JPG or DOCX)")

    digest = hashlib.sha256(data).hexdigest()

    # Exact-content dedup within the tenant (RLS already scopes the query).
    existing = await session.scalar(select(Document).where(Document.content_sha256 == digest))
    if existing is not None:
        return Ingested(document=existing, duplicate=True)

    # The matter must belong to the caller's tenant.
    if await session.scalar(select(Matter.id).where(Matter.id == matter_id)) is None:
        raise IngestError(404, "matter not found")

    is_scanned: bool | None = None
    page_count: int | None = None
    if fmt is SourceFormat.PDF:
        page_count, is_scanned = await run_in_threadpool(detect.pdf_page_stats, data)

    mime = detect.FORMAT_TO_MIME[fmt]
    storage_key = f"{tenant_id}/{digest}.{_EXT[fmt]}"
    await run_in_threadpool(storage.upload_bytes, storage_key, data, mime)

    document = Document(
        tenant_id=tenant_id,
        matter_id=matter_id,
        original_filename=filename,
        mime_type=mime,
        source_format=fmt,
        byte_size=len(data),
        content_sha256=digest,
        storage_key=storage_key,
        is_scanned=is_scanned,
        page_count=page_count,
    )
    session.add(document)
    await session.flush()  # assigns document.id

    session.add_all(
        [
            AuditLog(
                tenant_id=tenant_id,
                document_id=document.id,
                actor=actor,
                event="document.uploaded",
                detail={"filename": filename, "bytes": len(data), "sha256": digest},
            ),
            AuditLog(
                tenant_id=tenant_id,
                document_id=document.id,
                actor="system",
                event="document.stored",
                detail={"storage_key": storage_key},
            ),
        ]
    )
    return Ingested(document=document, duplicate=False)
