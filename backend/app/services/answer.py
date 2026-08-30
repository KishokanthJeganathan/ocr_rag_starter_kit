"""Turn retrieved chunks + a question into a grounded answer with citations.

Blocking (OpenAI call) — invoke through run_in_threadpool.
"""

from __future__ import annotations

from dataclasses import dataclass

from openai import OpenAI

from app.config import settings
from app.services.retrieve import RetrievedChunk

_SNIPPET_CHARS = 240

_SYSTEM_PROMPT = (
    "You answer questions about the user's documents using only the numbered "
    "sources below. Cite the sources you rely on inline as [S1], [S2], and so on. "
    "If the sources do not contain the answer, say so plainly. Never use outside "
    "knowledge."
)


@dataclass(frozen=True)
class Source:
    n: int
    document_id: str
    filename: str
    page: int
    snippet: str


@dataclass(frozen=True)
class Answer:
    answer: str
    sources: list[Source]


def _client() -> OpenAI:
    return OpenAI(api_key=settings.openai_api_key)


def generate_answer(question: str, chunks: list[RetrievedChunk]) -> Answer:
    if not chunks:
        return Answer(answer="No documents matched that question.", sources=[])

    blocks: list[str] = []
    sources: list[Source] = []
    for i, chunk in enumerate(chunks, start=1):
        blocks.append(f"[S{i}] {chunk.filename} p.{chunk.page}\n{chunk.text}")
        sources.append(
            Source(
                n=i,
                document_id=str(chunk.document_id),
                filename=chunk.filename,
                page=chunk.page,
                snippet=chunk.text[:_SNIPPET_CHARS].strip(),
            )
        )

    response = _client().chat.completions.create(
        model=settings.answer_model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Sources:\n{chr(10).join(blocks)}\n\nQuestion: {question}",
            },
        ],
    )
    return Answer(answer=response.choices[0].message.content or "", sources=sources)
