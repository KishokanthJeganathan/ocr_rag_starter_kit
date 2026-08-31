"""ARQ connection pool for enqueuing background jobs from the API."""

from __future__ import annotations

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.config import settings

_pool: ArqRedis | None = None


async def get_pool() -> ArqRedis:
    global _pool
    if _pool is None:
        _pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None


async def enqueue_process_document(document_id: object, tenant_id: object) -> None:
    pool = await get_pool()
    await pool.enqueue_job("process_document", str(document_id), str(tenant_id))
