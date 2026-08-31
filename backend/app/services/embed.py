"""Text -> embedding vectors via LangChain's OpenAI wrapper (batching + retries).

Blocking; call through run_in_threadpool.
"""

from __future__ import annotations

from langchain_openai import OpenAIEmbeddings

from app.config import settings


def _embeddings() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(model=settings.embed_model, openai_api_key=settings.openai_api_key)


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    return _embeddings().embed_documents(texts)


def embed_text(text: str) -> list[float]:
    return _embeddings().embed_query(text)
