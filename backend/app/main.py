"""FastAPI application entrypoint."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text

from app import __version__
from app.api.ask import router as ask_router
from app.api.documents import router as documents_router
from app.config import settings
from app.db import engine
from app.logging import configure_logging, get_logger
from app.queue import close_pool

configure_logging(settings.log_level)
log = get_logger("app.main")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    log.info("api.startup", environment=settings.environment, version=__version__)
    yield
    await close_pool()
    await engine.dispose()
    log.info("api.shutdown")


app = FastAPI(
    title="OCR-RAG Document Intelligence",
    version=__version__,
    lifespan=lifespan,
)

app.include_router(documents_router)
app.include_router(ask_router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """Liveness: the process is up. No dependency checks."""
    return {"status": "ok", "service": "api", "version": __version__}


@app.get("/health/ready", tags=["health"])
async def ready() -> JSONResponse:
    """Readiness: database and Redis are reachable."""
    checks: dict[str, str] = {}

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc.__class__.__name__}"

    redis: Redis = Redis.from_url(settings.redis_url)
    try:
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error: {exc.__class__.__name__}"
    finally:
        await redis.aclose()

    healthy = all(v == "ok" for v in checks.values())
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={"status": "ok" if healthy else "degraded", "checks": checks},
    )
