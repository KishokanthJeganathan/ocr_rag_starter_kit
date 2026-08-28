"""Shared FastAPI dependencies.

Tenant identity comes from the ``X-Tenant-Id`` header for now — a deliberate
stopgap until real auth lands later.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal, set_current_tenant


async def get_tenant_id(x_tenant_id: Annotated[str, Header()]) -> uuid.UUID:
    try:
        return uuid.UUID(x_tenant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="X-Tenant-Id must be a UUID") from None


async def tenant_session(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
) -> AsyncIterator[AsyncSession]:
    """A session with ``app.current_tenant`` set, so row-level security scopes
    every statement to the caller's tenant. The caller commits explicitly."""
    async with SessionLocal() as session:
        await set_current_tenant(session, tenant_id)
        yield session
