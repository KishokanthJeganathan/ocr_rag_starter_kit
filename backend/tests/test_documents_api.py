"""Ingestion API: upload, dedup, detection, tenant isolation.

S3 is mocked with moto, so no MinIO is needed. Each test uses a fresh random
tenant, so row-level security keeps tests isolated without cleanup.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator

import boto3
import pymupdf
import pytest
from httpx import AsyncClient
from moto import mock_aws

from app.config import settings
from app.db import session_scope
from app.models import Document, DocumentStatus, Matter, Tenant
from app.worker import process_document
from tests._textract import FakeTextractClient


@pytest.fixture
def s3(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    # Pin storage config so tests don't depend on the developer's .env.
    monkeypatch.setattr(settings, "s3_endpoint_url", None)
    monkeypatch.setattr(settings, "s3_region", "us-east-1")
    monkeypatch.setattr(settings, "s3_bucket", "test-bucket")
    with mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="test-bucket")
        yield


@pytest.fixture(autouse=True)
def captured_jobs(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    jobs: list[tuple[str, str]] = []

    async def _record(document_id: object, tenant_id: object) -> None:
        jobs.append((str(document_id), str(tenant_id)))

    monkeypatch.setattr("app.api.documents.enqueue_process_document", _record)
    return jobs


@pytest.fixture
async def demo() -> AsyncIterator[tuple[uuid.UUID, uuid.UUID]]:
    tenant_id, matter_id = uuid.uuid4(), uuid.uuid4()
    async with session_scope(tenant_id) as session:
        session.add(Tenant(id=tenant_id, name=f"t-{tenant_id}"))
        await session.flush()
        session.add(Matter(id=matter_id, tenant_id=tenant_id, name="Matter"))
    yield tenant_id, matter_id


def _pdf(text: str = "Selectable born-digital text. " * 40) -> bytes:
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 100), text)
    return bytes(doc.tobytes())


async def _upload(
    client: AsyncClient,
    tenant_id: uuid.UUID,
    matter_id: uuid.UUID,
    data: bytes,
    filename: str = "nda.pdf",
) -> object:
    return await client.post(
        "/v1/documents",
        headers={"X-Tenant-Id": str(tenant_id)},
        data={"matter_id": str(matter_id)},
        files={"file": (filename, data, "application/octet-stream")},
    )


async def test_upload_pdf_creates_document_and_enqueues(
    client: AsyncClient,
    s3: None,
    demo: tuple[uuid.UUID, uuid.UUID],
    captured_jobs: list[tuple[str, str]],
) -> None:
    tenant_id, matter_id = demo
    resp = await _upload(client, tenant_id, matter_id, _pdf())

    assert resp.status_code == 201
    body = resp.json()["document"]
    assert resp.json()["duplicate"] is False
    assert body["source_format"] == "pdf"
    assert body["is_scanned"] is False
    assert body["page_count"] == 1
    assert body["status"] == "queued"

    assert captured_jobs == [(body["id"], str(tenant_id))]

    stored = boto3.client("s3", region_name=settings.s3_region).list_objects_v2(
        Bucket=settings.s3_bucket
    )
    assert any(body["content_sha256"] in obj["Key"] for obj in stored["Contents"])


async def test_identical_bytes_are_deduped(
    client: AsyncClient,
    s3: None,
    demo: tuple[uuid.UUID, uuid.UUID],
    captured_jobs: list[tuple[str, str]],
) -> None:
    tenant_id, matter_id = demo
    data = _pdf()
    first = await _upload(client, tenant_id, matter_id, data)
    second = await _upload(client, tenant_id, matter_id, data)

    assert first.json()["document"]["id"] == second.json()["document"]["id"]
    assert second.json()["duplicate"] is True
    assert len(captured_jobs) == 1  # the duplicate is not re-queued


async def test_textless_pdf_is_flagged_scanned(
    client: AsyncClient, s3: None, demo: tuple[uuid.UUID, uuid.UUID]
) -> None:
    tenant_id, matter_id = demo
    doc = pymupdf.open()
    doc.new_page()
    resp = await _upload(client, tenant_id, matter_id, bytes(doc.tobytes()))
    assert resp.json()["document"]["is_scanned"] is True


async def test_unsupported_type_is_415(
    client: AsyncClient, s3: None, demo: tuple[uuid.UUID, uuid.UUID]
) -> None:
    tenant_id, matter_id = demo
    resp = await _upload(client, tenant_id, matter_id, b"notes not a doc\n" * 6, "x.txt")
    assert resp.status_code == 415


async def test_matter_from_another_tenant_is_404(
    client: AsyncClient, s3: None, demo: tuple[uuid.UUID, uuid.UUID]
) -> None:
    tenant_id, _ = demo
    resp = await _upload(client, tenant_id, uuid.uuid4(), _pdf())
    assert resp.status_code == 404


async def test_bad_tenant_header_is_400(client: AsyncClient, s3: None) -> None:
    resp = await client.post(
        "/v1/documents",
        headers={"X-Tenant-Id": "not-a-uuid"},
        data={"matter_id": str(uuid.uuid4())},
        files={"file": ("a.pdf", _pdf(), "application/octet-stream")},
    )
    assert resp.status_code == 400


async def test_list_and_get_are_tenant_scoped(
    client: AsyncClient, s3: None, demo: tuple[uuid.UUID, uuid.UUID]
) -> None:
    tenant_id, matter_id = demo
    created = await _upload(client, tenant_id, matter_id, _pdf())
    doc_id = created.json()["document"]["id"]

    mine = await client.get("/v1/documents", headers={"X-Tenant-Id": str(tenant_id)})
    assert [d["id"] for d in mine.json()] == [doc_id]

    stranger = uuid.uuid4()
    hidden = await client.get(f"/v1/documents/{doc_id}", headers={"X-Tenant-Id": str(stranger)})
    assert hidden.status_code == 404


async def test_worker_runs_ocr_and_stores_layout(
    client: AsyncClient,
    s3: None,
    demo: tuple[uuid.UUID, uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.services.ocr._textract_client", lambda: FakeTextractClient())
    tenant_id, matter_id = demo
    created = await _upload(client, tenant_id, matter_id, _pdf())
    doc_id = created.json()["document"]["id"]

    await process_document({}, doc_id, str(tenant_id))

    layout = await client.get(
        f"/v1/documents/{doc_id}/layout", headers={"X-Tenant-Id": str(tenant_id)}
    )
    assert layout.status_code == 200
    body = layout.json()
    assert body["engine"] == "textract"
    assert body["page_count"] == 1
    assert body["pages"][0]["blocks"][0]["role"] == "title"
    assert body["pages"][0]["image_key"].endswith("/pages/1.png")

    doc = await client.get(f"/v1/documents/{doc_id}", headers={"X-Tenant-Id": str(tenant_id)})
    assert doc.json()["status"] == "processing"
    assert doc.json()["page_count"] == 1


async def test_worker_marks_document_failed_on_ocr_error(
    client: AsyncClient,
    s3: None,
    demo: tuple[uuid.UUID, uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(_: object) -> None:
        raise RuntimeError("textract exploded")

    monkeypatch.setattr("app.services.ocr.analyze_pages", _boom)
    tenant_id, matter_id = demo
    created = await _upload(client, tenant_id, matter_id, _pdf())
    doc_id = created.json()["document"]["id"]

    with pytest.raises(RuntimeError):
        await process_document({}, doc_id, str(tenant_id))

    async with session_scope(tenant_id) as session:
        document = await session.get(Document, uuid.UUID(doc_id))
        assert document is not None
        assert document.status is DocumentStatus.FAILED
        assert "textract exploded" in (document.error or "")
