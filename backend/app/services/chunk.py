"""Split a document's OCR layout into overlapping passages for retrieval.

LangChain's ``RecursiveCharacterTextSplitter`` does the splitting — it prefers to
break on paragraph, then line, then word boundaries rather than mid-sentence,
and sizes windows in tokens. We keep the page bookkeeping: each chunk is located
back in the joined text (forward-only) so it can record the page it starts on,
which becomes the citation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter

_CHUNK_TOKENS = 256
_OVERLAP_TOKENS = 40
_LOCATE_PREFIX = 120  # chars of a chunk used to find it back in the joined text
_SKIP_ROLES = {"footer", "page_number"}  # running headers/footers aren't content

_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    encoding_name="cl100k_base",
    chunk_size=_CHUNK_TOKENS,
    chunk_overlap=_OVERLAP_TOKENS,
)


@dataclass(frozen=True)
class Chunk:
    index: int
    page: int
    text: str


def chunk_layout(layout: dict[str, Any]) -> list[Chunk]:
    """``layout`` is the ``document_layouts.layout`` JSON (``OcrLayout.to_dict()``)."""
    parts: list[str] = []
    # (char offset in the joined string) -> page number
    markers: list[tuple[int, int]] = []
    cursor = 0
    for page in layout.get("pages", []):
        page_no = int(page["number"])
        for block in page.get("blocks", []):
            if block.get("role") in _SKIP_ROLES:
                continue
            text = (block.get("text") or "").strip()
            if not text:
                continue
            markers.append((cursor, page_no))
            parts.append(text)
            cursor += len(text) + 1  # + the "\n" the join adds

    full = "\n".join(parts)
    if not full.strip():
        return []

    chunks: list[Chunk] = []
    cursor = 0
    for i, piece in enumerate(_splitter.split_text(full)):
        cursor = _locate(full, piece, cursor)
        chunks.append(Chunk(index=i, page=_page_at(markers, cursor), text=piece))
    return chunks


def _locate(full: str, piece: str, cursor: int) -> int:
    """Character offset of ``piece`` in ``full``, searching forward from
    ``cursor`` so repeated text never rewinds the page counter."""
    probe = piece[:_LOCATE_PREFIX].strip()
    if not probe:
        return cursor
    found = full.find(probe, cursor)
    if found == -1:
        found = full.find(probe)  # whitespace drift at a boundary
    return max(cursor, found)


def _page_at(markers: list[tuple[int, int]], offset: int) -> int:
    page = markers[0][1] if markers else 1
    for marker_offset, marker_page in markers:
        if marker_offset > offset:
            break
        page = marker_page
    return page
