"""ARQ worker.

``process_document`` runs the OCR & layout step: rasterize the original,
Textract each page, store the normalized layout + page images. Everything after
this (classification, extraction, validation) lands in later stages.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Coroutine
from typing import Any, ClassVar

from arq.connections import RedisSettings
from fastapi.concurrency import run_in_threadpool

from app.config import settings
from app.db import session_scope
from app.logging import configure_logging, get_logger
from app.models import AuditLog, Document, DocumentLayout, DocumentStatus
from app.services import ocr, storage

configure_logging(settings.log_level)
log = get_logger("app.worker")


async def ping(_: dict[str, Any]) -> str:
    return "pong"


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
        session.add(
            AuditLog(
                tenant_id=tid,
                document_id=did,
                actor="system",
                event="ocr.started",
                detail={"engine": "textract"},
            )
        )

    try:
        data = await run_in_threadpool(storage.download_bytes, storage_key)
        pages = await run_in_threadpool(ocr.rasterize, data)
        layout = await run_in_threadpool(ocr.analyze_pages, pages)

        image_keys: dict[int, str] = {}
        for number, page in enumerate(pages, start=1):
            key = f"{tid}/{content_sha256}/pages/{number}.png"
            await run_in_threadpool(storage.upload_bytes, key, page.png, "image/png")
            image_keys[number] = key

        async with session_scope(tid) as session:
            document = await session.get(Document, did)
            if document is None:
                return
            document.page_count = len(layout.pages)
            session.add(
                DocumentLayout(
                    tenant_id=tid,
                    document_id=did,
                    engine=layout.engine,
                    page_count=len(layout.pages),
                    layout=layout.to_dict(image_keys),
                )
            )
            session.add(
                AuditLog(
                    tenant_id=tid,
                    document_id=did,
                    actor="system",
                    event="ocr.completed",
                    detail={"engine": layout.engine, "pages": len(layout.pages)},
                )
            )
        log.info("worker.ocr_done", document_id=document_id, pages=len(layout.pages))

    except Exception as exc:
        async with session_scope(tid) as session:
            document = await session.get(Document, did)
            if document is not None:
                document.status = DocumentStatus.FAILED
                document.error = f"{type(exc).__name__}: {exc}"
            session.add(
                AuditLog(
                    tenant_id=tid,
                    document_id=did,
                    actor="system",
                    event="ocr.failed",
                    detail={"error": f"{type(exc).__name__}: {exc}"},
                )
            )
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
