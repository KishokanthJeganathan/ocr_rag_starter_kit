"""File-type detection and the scanned-vs-digital heuristic."""

from __future__ import annotations

import base64
import io
import zipfile

import pymupdf

from app.models.enums import SourceFormat
from app.services import detect

# A real 1x1 PNG (signature + IHDR + IDAT + IEND), so libmagic recognises it.
_PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+P+/HgAFhAJ/wlseKgAAAABJRU5ErkJggg=="
)


def _minimal_docx() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<document/>")
    return buf.getvalue()


def _digital_pdf() -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Real, selectable, born-digital text. " * 40)
    return bytes(doc.tobytes())


def _blank_pdf() -> bytes:
    doc = pymupdf.open()
    doc.new_page()  # no text at all
    return bytes(doc.tobytes())


def test_detects_pdf() -> None:
    assert detect.detect_format(_digital_pdf()) is SourceFormat.PDF


def test_detects_png() -> None:
    assert detect.detect_format(_PNG_1PX) is SourceFormat.PNG


def test_detects_jpeg() -> None:
    jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00" + b"\x00" * 32
    assert detect.detect_format(jpeg) is SourceFormat.JPG


def test_detects_docx_even_when_libmagic_says_zip() -> None:
    assert detect.detect_format(_minimal_docx()) is SourceFormat.DOCX


def test_rejects_plain_text() -> None:
    assert detect.detect_format(b"just some notes, not a document\n" * 8) is None


def test_digital_pdf_is_not_scanned() -> None:
    pages, is_scanned = detect.pdf_page_stats(_digital_pdf())
    assert pages == 1
    assert is_scanned is False


def test_textless_pdf_reads_as_scanned() -> None:
    pages, is_scanned = detect.pdf_page_stats(_blank_pdf())
    assert pages == 1
    assert is_scanned is True
