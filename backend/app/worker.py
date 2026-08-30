"""ARQ worker.

``process_document`` runs the post-upload pipeline: rasterize the original,
Textract each page, store the normalized layout + page images, classify the
document type, then (for an NDA) extract its fields and validate them, and chunk
+ embed the text for retrieval. Everything after OCR is best-effort — OCR has
already succeeded by then.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Coroutine
from typing import Any, ClassVar

from arq.connections import RedisSettings
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import delete

from app.config import settings
from app.db import session_scope
from app.logging import configure_logging, get_logger
from app.models import (
    Document,
    DocumentChunk,
    DocumentExtraction,
    DocumentLayout,
    DocumentStatus,
    DocumentType,
    DocumentValidation,
)
from app.services import chunk, classify, embed, extract, ocr, storage, validate

configure_logging(settings.log_level)
log = get_logger("app.worker")


async def ping(_: dict[str, Any]) -> str:
    return "pong"


async def _classify(layout: ocr.OcrLayout) -> classify.Classification | None:
    """Best-effort: a classifier failure must not lose a successful OCR."""
    try:
        result = await run_in_threadpool(classify.classify_document, layout)
    except Exception as exc:
        log.warning("worker.classify_failed", error=f"{type(exc).__name__}: {exc}")
        return None
    log.info("worker.classified", doc_type=result.doc_type, confidence=result.confidence)
    return result


async def _extract(
    layout: ocr.OcrLayout, classification: classify.Classification | None
) -> extract.NdaExtraction | None:
    """Best-effort, and only for the types we have a schema for (NDA today)."""
    if classification is None or classification.doc_type != DocumentType.NDA:
        return None
    try:
        result = await run_in_threadpool(extract.extract_nda, layout)
    except Exception as exc:
        log.warning("worker.extract_failed", error=f"{type(exc).__name__}: {exc}")
        return None
    log.info("worker.extracted", schema="nda.v1")
    return result


async def _index(layout_dict: dict[str, Any]) -> list[tuple[chunk.Chunk, list[float]]] | None:
    """Chunk the layout and embed each piece. Best-effort — a failure just
    leaves the document out of retrieval."""
    chunks = chunk.chunk_layout(layout_dict)
    if not chunks:
        return None
    try:
        vectors = await run_in_threadpool(embed.embed_texts, [c.text for c in chunks])
    except Exception as exc:
        log.warning("worker.embed_failed", error=f"{type(exc).__name__}: {exc}")
        return None
    log.info("worker.indexed", chunks=len(chunks))
    return list(zip(chunks, vectors, strict=True))


async def process_document(_: dict[str, Any], document_id: str, tenant_id: str) -> None:
    tid = uuid.UUID(tenant_id)
    did = uuid.UUID(document_id)

    async with session_scope(tid) as session:
        document = await session.get(Document, did)
        if document is None:
            log.warning("worker.document_missing", document_id=document_id)
            return
        document.status = DocumentStatus.PROCESSING
        storage_key = document.storage_key
        content_sha256 = document.content_sha256

    try:
        data = await run_in_threadpool(storage.download_bytes, storage_key)
        pages = await run_in_threadpool(ocr.rasterize, data)
        layout = await run_in_threadpool(ocr.analyze_pages, pages)

        image_keys: dict[int, str] = {}
        for number, page in enumerate(pages, start=1):
            key = f"{tid}/{content_sha256}/pages/{number}.png"
            await run_in_threadpool(storage.upload_bytes, key, page.png, "image/png")
            image_keys[number] = key

        layout_dict = layout.to_dict(image_keys)
        classification = await _classify(layout)
        extraction = await _extract(layout, classification)
        validation = validate.validate_nda(extraction) if extraction is not None else None
        indexed = await _index(layout_dict)

        async with session_scope(tid) as session:
            document = await session.get(Document, did)
            if document is None:
                return
            document.page_count = len(layout.pages)
            document.status = DocumentStatus.PROCESSED
            if classification is not None:
                document.doc_type = classification.doc_type
                document.doc_type_confidence = classification.confidence
            session.add(
                DocumentLayout(
                    tenant_id=tid,
                    document_id=did,
                    engine=layout.engine,
                    page_count=len(layout.pages),
                    layout=layout_dict,
                )
            )
            if indexed is not None:
                await session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == did))
                for piece, vector in indexed:
                    session.add(
                        DocumentChunk(
                            tenant_id=tid,
                            document_id=did,
                            chunk_index=piece.index,
                            page=piece.page,
                            text=piece.text,
                            embedding=vector,
                        )
                    )
            if extraction is not None:
                session.add(
                    DocumentExtraction(
                        tenant_id=tid,
                        document_id=did,
                        schema_version="nda.v1",
                        model=settings.extractor_model,
                        fields=extraction.model_dump(mode="json"),
                    )
                )
            if validation is not None:
                dumped = validation.model_dump(mode="json")
                session.add(
                    DocumentValidation(
                        tenant_id=tid,
                        document_id=did,
                        verdict=dumped["verdict"],
                        issues=dumped["issues"],
                    )
                )
        log.info(
            "worker.processed",
            document_id=document_id,
            pages=len(layout.pages),
            doc_type=classification.doc_type if classification else None,
            extracted=extraction is not None,
            verdict=validation.verdict if validation else None,
            chunks=len(indexed) if indexed else 0,
        )

    except Exception as exc:
        async with session_scope(tid) as session:
            document = await session.get(Document, did)
            if document is not None:
                document.status = DocumentStatus.FAILED
                document.error = f"{type(exc).__name__}: {exc}"
        log.error("worker.ocr_failed", document_id=document_id, error=str(exc))
        raise


async def on_startup(ctx: dict[str, Any]) -> None:
    log.info("worker.startup", environment=settings.environment)


async def on_shutdown(ctx: dict[str, Any]) -> None:
    log.info("worker.shutdown")


class WorkerSettings:
    functions: ClassVar[list[Callable[..., Coroutine[Any, Any, Any]]]] = [
        ping,
        process_document,
    ]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    on_startup = staticmethod(on_startup)
    on_shutdown = staticmethod(on_shutdown)
    max_jobs = 10
    job_timeout = 600
