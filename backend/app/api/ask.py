"""RAG Q&A: embed the question, retrieve the nearest chunks (this tenant only,
optionally one document), and answer from them with citations."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_tenant_id, tenant_session
from app.schemas import AskRequest, AskResponse, SourceOut
from app.services import answer, embed, retrieve

router = APIRouter(prefix="/v1", tags=["ask"])


@router.post("/ask", response_model=AskResponse)
async def ask(
    body: AskRequest,
    _tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    session: Annotated[AsyncSession, Depends(tenant_session)],
) -> AskResponse:
    question = body.question.strip()
    if not question:
        raise HTTPException(400, "question is required")

    query_embedding = await run_in_threadpool(embed.embed_text, question)
    chunks = await retrieve.retrieve(
        session, query_embedding=query_embedding, document_id=body.document_id
    )
    result = await run_in_threadpool(answer.generate_answer, question, chunks)

    return AskResponse(
        answer=result.answer,
        sources=[SourceOut(**vars(source)) for source in result.sources],
    )
