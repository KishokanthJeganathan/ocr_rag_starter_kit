"""Shared test fixtures.

Tests run against a live PostgreSQL that already has migration ``0001`` applied
(``make up && make migrate`` locally; a service container in CI). The database
fixtures never commit — everything happens inside one transaction that is rolled
back, so no test data persists and the tenant guc stays transaction-local.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import engine as app_engine
from app.main import app


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def app_session() -> AsyncIterator[AsyncSession]:
    """A session on the RLS-enforced application role. Rolled back after each
    test so rows created under a tenant context never leak."""
    maker = async_sessionmaker(app_engine, expire_on_commit=False)
    async with maker() as session:
        try:
            yield session
        finally:
            await session.rollback()
