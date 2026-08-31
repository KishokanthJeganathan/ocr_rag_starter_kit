from __future__ import annotations

from httpx import AsyncClient


async def test_health_is_ok(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "api"


async def test_ready_reports_dependency_checks(client: AsyncClient) -> None:
    resp = await client.get("/health/ready")
    assert resp.status_code in (200, 503)
    checks = resp.json()["checks"]
    assert "database" in checks
    assert "redis" in checks


async def test_ready_database_is_reachable(client: AsyncClient) -> None:
    # The test suite requires a live DB, so readiness must see it as ok.
    resp = await client.get("/health/ready")
    assert resp.json()["checks"]["database"] == "ok"
