"""Row-level security is the tenant isolation boundary. These tests prove that
the application role cannot read or write across tenants.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio


async def _use_tenant(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    await session.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"),
        {"tid": str(tenant_id)},
    )


async def _insert_tenant(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    await session.execute(
        text("INSERT INTO tenants (id, name, created_at) VALUES (:id, :name, now())"),
        {"id": tenant_id, "name": f"tenant-{tenant_id}"},
    )


async def _insert_matter(session: AsyncSession, tenant_id: uuid.UUID, name: str) -> None:
    await session.execute(
        text(
            "INSERT INTO matters (id, tenant_id, name, created_at) VALUES (:id, :tid, :name, now())"
        ),
        {"id": uuid.uuid4(), "tid": tenant_id, "name": name},
    )


async def test_reads_are_scoped_to_the_current_tenant(app_session: AsyncSession) -> None:
    t1, t2 = uuid.uuid4(), uuid.uuid4()

    await _use_tenant(app_session, t1)
    await _insert_tenant(app_session, t1)
    await _insert_matter(app_session, t1, "Matter One")

    await _use_tenant(app_session, t2)
    await _insert_tenant(app_session, t2)
    await _insert_matter(app_session, t2, "Matter Two")
    await app_session.flush()

    # Under tenant 2, only tenant 2's matter is visible.
    visible = (
        (await app_session.execute(text("SELECT name FROM matters ORDER BY name"))).scalars().all()
    )
    assert visible == ["Matter Two"]

    # Switching context switches what is visible — no leakage.
    await _use_tenant(app_session, t1)
    visible = (
        (await app_session.execute(text("SELECT name FROM matters ORDER BY name"))).scalars().all()
    )
    assert visible == ["Matter One"]


async def test_an_unrelated_tenant_sees_nothing(app_session: AsyncSession) -> None:
    t1 = uuid.uuid4()
    await _use_tenant(app_session, t1)
    await _insert_tenant(app_session, t1)
    await _insert_matter(app_session, t1, "Hidden")
    await app_session.flush()

    # Switch to a tenant that owns no rows: default-deny, nothing visible.
    await _use_tenant(app_session, uuid.uuid4())
    count = (await app_session.execute(text("SELECT count(*) FROM matters"))).scalar_one()
    assert count == 0


async def test_write_check_rejects_a_foreign_tenant_id(
    app_session: AsyncSession,
) -> None:
    t1, t2 = uuid.uuid4(), uuid.uuid4()
    await _use_tenant(app_session, t1)
    await _insert_tenant(app_session, t1)
    await app_session.flush()

    # Still in tenant 1's context, try to write a row tagged for tenant 2.
    with pytest.raises(DBAPIError):
        await _insert_matter(app_session, t2, "Smuggled")
        await app_session.flush()
