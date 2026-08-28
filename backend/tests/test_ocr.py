"""OCR service: rasterization and Textract response normalization."""

from __future__ import annotations

import pymupdf
import pytest

from app.services import ocr
from tests._textract import FakeTextractClient


def _two_page_pdf() -> bytes:
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 100), "Page one.")
    doc.new_page().insert_text((72, 100), "Page two.")
    return bytes(doc.tobytes())


def test_rasterize_one_image_per_page() -> None:
    pages = ocr.rasterize(_two_page_pdf())
    assert len(pages) == 2
    for page in pages:
        assert page.png.startswith(b"\x89PNG")
        assert page.width > 0 and page.height > 0


def test_analyze_pages_normalizes_textract_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ocr, "_textract_client", lambda: FakeTextractClient())

    layout = ocr.analyze_pages([ocr.PageImage(png=b"fake", width=850, height=1100)])

    assert layout.engine == "textract"
    assert len(layout.pages) == 1

    blocks = layout.pages[0].blocks
    assert [b.role for b in blocks] == ["title", "text"]
    assert blocks[0].text == "NON-DISCLOSURE AGREEMENT"
    assert blocks[1].text == "This Agreement is entered into as of March 1, 2026."

    for block in blocks:
        assert 0.0 <= block.confidence <= 1.0
        x0, y0, x1, y1 = block.bbox
        assert 0.0 <= x0 < x1 <= 1.0
        assert 0.0 <= y0 < y1 <= 1.0


def test_layout_to_dict_carries_image_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ocr, "_textract_client", lambda: FakeTextractClient())
    layout = ocr.analyze_pages([ocr.PageImage(png=b"fake", width=850, height=1100)])

    as_dict = layout.to_dict({1: "tenant/abc/pages/1.png"})
    assert as_dict["pages"][0]["image_key"] == "tenant/abc/pages/1.png"
    assert as_dict["pages"][0]["blocks"][0]["bbox"] == list(layout.pages[0].blocks[0].bbox)
