"""Async database engine, session factory, and tenant-scoped session helper."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: a session with no tenant context (RLS denies all
    tenant-scoped rows). Use for health checks and non-tenant work only."""
    async with SessionLocal() as session:
        yield session


@asynccontextmanager
async def session_scope(tenant_id: UUID | None = None) -> AsyncIterator[AsyncSession]:
    """Transactional session. When ``tenant_id`` is given, every statement runs
    with ``app.current_tenant`` set for the transaction, so row-level security
    scopes reads and writes to that tenant. Commits on success, rolls back on
    error.
    """
    async with SessionLocal() as session:
        if tenant_id is not None:
            await session.execute(
                text("SELECT set_config('app.current_tenant', :tid, true)"),
                {"tid": str(tenant_id)},
            )
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def set_current_tenant(session: AsyncSession, tenant_id: UUID) -> None:
    """Set the tenant guc on an existing open transaction (transaction-local)."""
    await session.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"),
        {"tid": str(tenant_id)},
    )
