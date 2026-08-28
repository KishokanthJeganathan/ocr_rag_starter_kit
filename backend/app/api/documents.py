"""Document ingestion and listing endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.deps import get_actor, get_tenant_id, tenant_session
from app.models import Document
from app.queue import enqueue_process_document
from app.schemas import DocumentOut, UploadResult
from app.services.ingest import IngestError, ingest_document

router = APIRouter(prefix="/v1/documents", tags=["documents"])


@router.post("", response_model=UploadResult, status_code=201)
async def upload_document(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    actor: Annotated[str, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(tenant_session)],
    matter_id: Annotated[uuid.UUID, Form()],
    file: Annotated[UploadFile, File()],
) -> UploadResult:
    data = await file.read()
    if not data:
        raise HTTPException(400, "empty file")
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(413, f"file exceeds {settings.max_upload_bytes} bytes")

    try:
        ingested = await ingest_document(
            session,
            tenant_id=tenant_id,
            matter_id=matter_id,
            filename=file.filename or "upload",
            data=data,
            actor=actor,
        )
    except IngestError as exc:
        raise HTTPException(exc.status_code, exc.detail) from None

    await session.commit()

    if not ingested.duplicate:
        await enqueue_process_document(ingested.document.id, tenant_id)

    return UploadResult(
        document=DocumentOut.model_validate(ingested.document),
        duplicate=ingested.duplicate,
    )


@router.get("", response_model=list[DocumentOut])
async def list_documents(
    session: Annotated[AsyncSession, Depends(tenant_session)],
) -> list[Document]:
    rows = await session.scalars(select(Document).order_by(Document.created_at.desc()))
    return list(rows)


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(tenant_session)],
) -> Document:
    document = await session.get(Document, document_id)
    if document is None:
        raise HTTPException(404, "document not found")
    return document
