"""POST /v1/ask — retrieval runs for real against pgvector; the OpenAI calls
(question embedding, answer generation) are faked."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from types import SimpleNamespace

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.config import settings
from app.db import session_scope
from app.models import Document, DocumentChunk, Matter, SourceFormat, Tenant


def _vec(fill: float) -> list[float]:
    return [fill] * settings.embed_dim


def _fake_chat(content: str) -> SimpleNamespace:
    completions = SimpleNamespace(
        create=lambda **_: SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )
    )
    return SimpleNamespace(chat=SimpleNamespace(completions=completions))


@pytest_asyncio.fixture
async def tenant() -> AsyncIterator[tuple[uuid.UUID, uuid.UUID]]:
    tenant_id, matter_id = uuid.uuid4(), uuid.uuid4()
    async with session_scope(tenant_id) as session:
        session.add(Tenant(id=tenant_id, name=f"t-{tenant_id}"))
        await session.flush()
        session.add(Matter(id=matter_id, tenant_id=tenant_id, name="M"))
    yield tenant_id, matter_id


async def _add_document_with_chunks(tenant_id: uuid.UUID, matter_id: uuid.UUID) -> uuid.UUID:
    async with session_scope(tenant_id) as session:
        document = Document(
            tenant_id=tenant_id,
            matter_id=matter_id,
            original_filename="seed.pdf",
            mime_type="application/pdf",
            source_format=SourceFormat.PDF,
            byte_size=10,
            content_sha256="0" * 64,
            storage_key=f"{tenant_id}/seed.pdf",
        )
        session.add(document)
        await session.flush()
        session.add(
            DocumentChunk(
                tenant_id=tenant_id,
                document_id=document.id,
                chunk_index=0,
                page=2,
                text="This Agreement is governed by the laws of the State of New York.",
                embedding=_vec(0.1),
            )
        )
        session.add(
            DocumentChunk(
                tenant_id=tenant_id,
                document_id=document.id,
                chunk_index=1,
                page=1,
                text="Definitions of Confidential Information.",
                embedding=_vec(-0.1),
            )
        )
        return document.id


async def test_ask_answers_from_the_nearest_chunk(
    client: AsyncClient,
    tenant: tuple[uuid.UUID, uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id, matter_id = tenant
    await _add_document_with_chunks(tenant_id, matter_id)
    monkeypatch.setattr("app.services.embed.embed_text", lambda _q: _vec(0.1))
    monkeypatch.setattr(
        "app.services.answer._client", lambda: _fake_chat("Governed by New York [S1].")
    )

    resp = await client.post(
        "/v1/ask",
        headers={"X-Tenant-Id": str(tenant_id)},
        json={"question": "what law governs this agreement?"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert "New York" in body["answer"]
    assert body["sources"][0]["filename"] == "seed.pdf"
    assert body["sources"][0]["page"] == 2


async def test_ask_with_no_matching_documents(
    client: AsyncClient,
    tenant: tuple[uuid.UUID, uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id, _ = tenant
    monkeypatch.setattr("app.services.embed.embed_text", lambda _q: _vec(0.1))

    resp = await client.post(
        "/v1/ask",
        headers={"X-Tenant-Id": str(tenant_id)},
        json={"question": "anything at all"},
    )

    assert resp.status_code == 200
    assert resp.json()["sources"] == []


async def test_ask_rejects_a_blank_question(
    client: AsyncClient, tenant: tuple[uuid.UUID, uuid.UUID]
) -> None:
    tenant_id, _ = tenant
    resp = await client.post(
        "/v1/ask",
        headers={"X-Tenant-Id": str(tenant_id)},
        json={"question": "   "},
    )
    assert resp.status_code == 400
