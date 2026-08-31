"""Nearest-neighbour search over document_chunks (pgvector, cosine distance).

Tenant scoping is automatic — RLS filters every row by the session's
``app.current_tenant``. An optional ``document_id`` narrows to one document.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Document, DocumentChunk


@dataclass(frozen=True)
class RetrievedChunk:
    document_id: uuid.UUID
    filename: str
    page: int
    text: str
    distance: float


async def retrieve(
    session: AsyncSession,
    *,
    query_embedding: list[float],
    document_id: uuid.UUID | None = None,
    k: int | None = None,
) -> list[RetrievedChunk]:
    distance = DocumentChunk.embedding.cosine_distance(query_embedding)
    stmt = (
        select(
            DocumentChunk.document_id,
            Document.original_filename,
            DocumentChunk.page,
            DocumentChunk.text,
            distance.label("distance"),
        )
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(distance < settings.retrieval_max_distance)
        .order_by(distance)
        .limit(k or settings.retrieval_k)
    )
    if document_id is not None:
        stmt = stmt.where(DocumentChunk.document_id == document_id)

    rows = (await session.execute(stmt)).all()
    return [
        RetrievedChunk(
            document_id=row[0], filename=row[1], page=row[2], text=row[3], distance=row[4]
        )
        for row in rows
    ]
