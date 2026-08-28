"""ARQ worker. Stage 0 wires the worker to Redis with a single ping task;
document-processing tasks are added from Stage 2 onward."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any, ClassVar

from arq.connections import RedisSettings

from app.config import settings
from app.logging import configure_logging, get_logger

configure_logging(settings.log_level)
log = get_logger("app.worker")


async def ping(_: dict[str, Any]) -> str:
    return "pong"


async def on_startup(ctx: dict[str, Any]) -> None:
    log.info("worker.startup", environment=settings.environment)


async def on_shutdown(ctx: dict[str, Any]) -> None:
    log.info("worker.shutdown")


class WorkerSettings:
    functions: ClassVar[list[Callable[..., Coroutine[Any, Any, Any]]]] = [ping]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    on_startup = staticmethod(on_startup)
    on_shutdown = staticmethod(on_shutdown)
    max_jobs = 10
    job_timeout = 300
