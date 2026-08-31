"""Layout -> chunks (LangChain splitter + our page bookkeeping). Pure, no DB."""

from __future__ import annotations

from typing import Any

from app.services.chunk import chunk_layout


def _layout(pages: list[list[str]]) -> dict[str, Any]:
    return {
        "pages": [
            {"number": i, "blocks": [{"text": t} for t in texts]}
            for i, texts in enumerate(pages, start=1)
        ]
    }


def test_empty_layout_yields_nothing() -> None:
    assert chunk_layout({"pages": []}) == []
    assert chunk_layout(_layout([[""], ["   "]])) == []


def test_short_document_is_one_chunk() -> None:
    chunks = chunk_layout(_layout([["Hello world.", "A second block."]]))
    assert len(chunks) == 1
    assert chunks[0].index == 0
    assert chunks[0].page == 1
    assert "Hello world." in chunks[0].text
    assert "A second block." in chunks[0].text


def test_long_document_splits_and_tracks_pages_in_order() -> None:
    page1 = " ".join(
        f"Clause {n}: the disclosing party shall protect confidential material." for n in range(60)
    )
    page2 = " ".join(
        f"Section {n}: the receiving party returns all documents on request." for n in range(60)
    )

    chunks = chunk_layout(_layout([[page1], [page2]]))

    assert len(chunks) >= 2
    assert [c.index for c in chunks] == list(range(len(chunks)))
    # pages only ever increase
    pages = [c.page for c in chunks]
    assert pages == sorted(pages)
    assert pages[0] == 1
    assert pages[-1] == 2
