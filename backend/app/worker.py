"""ARQ worker.

``process_document`` is the pipeline entry point. In Stage 2 it only records
that the job reached the worker; OCR and everything after it land in Stage 3.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Coroutine
from typing import Any, ClassVar

from arq.connections import RedisSettings

from app.config import settings
from app.db import session_scope
from app.logging import configure_logging, get_logger
from app.models import AuditLog

configure_logging(settings.log_level)
log = get_logger("app.worker")


async def ping(_: dict[str, Any]) -> str:
    return "pong"


async def process_document(_: dict[str, Any], document_id: str, tenant_id: str) -> None:
    tid = uuid.UUID(tenant_id)
    async with session_scope(tid) as session:
        session.add(
            AuditLog(
                tenant_id=tid,
                document_id=uuid.UUID(document_id),
                actor="system",
                event="worker.picked_up",
                detail={"note": "OCR runs from Stage 3"},
            )
        )
    log.info("worker.process_document", document_id=document_id, tenant_id=tenant_id)


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
    job_timeout = 300
