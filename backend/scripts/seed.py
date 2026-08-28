"""Create one demo tenant + matter so the API has something to accept uploads
against.

    cd backend && uv run python -m scripts.seed
"""

from __future__ import annotations

import asyncio
import uuid

from app.db import session_scope
from app.models import Matter, Tenant

DEMO_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DEMO_MATTER_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


async def main() -> None:
    async with session_scope(DEMO_TENANT_ID) as session:
        if await session.get(Tenant, DEMO_TENANT_ID) is None:
            session.add(Tenant(id=DEMO_TENANT_ID, name="Demo Tenant"))
            await session.flush()
        if await session.get(Matter, DEMO_MATTER_ID) is None:
            session.add(Matter(id=DEMO_MATTER_ID, tenant_id=DEMO_TENANT_ID, name="NDA Intake"))

    print(f"tenant_id : {DEMO_TENANT_ID}")
    print(f"matter_id : {DEMO_MATTER_ID}")
    print()
    print("Upload a fixture:")
    print(
        f"  curl -F file=@fixtures/nda_01000.pdf -F matter_id={DEMO_MATTER_ID} \\\n"
        f"       -H 'X-Tenant-Id: {DEMO_TENANT_ID}' http://localhost:8000/v1/documents"
    )


if __name__ == "__main__":
    asyncio.run(main())
