"""Work out what an uploaded file is, from its bytes.

- ``detect_format`` — file type via libmagic (python-magic).
- ``pdf_page_stats`` — page count and a scanned-vs-digital guess via PyMuPDF.
"""

from __future__ import annotations

import magic
import pymupdf

from app.models.enums import SourceFormat

_MIME_TO_FORMAT = {
    "application/pdf": SourceFormat.PDF,
    "image/png": SourceFormat.PNG,
    "image/jpeg": SourceFormat.JPG,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": SourceFormat.DOCX,
}

FORMAT_TO_MIME = {v: k for k, v in _MIME_TO_FORMAT.items()}
FORMAT_TO_MIME[SourceFormat.JPG] = "image/jpeg"

# libmagic averages ~50 real characters per page for anything OCR-worthy;
# a born-digital PDF has hundreds.
_SCANNED_CHARS_PER_PAGE = 50


def detect_format(data: bytes) -> SourceFormat | None:
    mime = magic.from_buffer(data, mime=True)
    if mime in _MIME_TO_FORMAT:
        return _MIME_TO_FORMAT[mime]
    # libmagic often reports a bare zip for .docx; confirm by structure.
    if mime == "application/zip" and data[:4] == b"PK\x03\x04" and b"word/" in data[:4096]:
        return SourceFormat.DOCX
    return None


def pdf_page_stats(data: bytes) -> tuple[int, bool]:
    """Return ``(page_count, is_scanned)``."""
    doc = pymupdf.open(stream=data, filetype="pdf")
    try:
        page_count = doc.page_count
        total_chars = sum(len(page.get_text().strip()) for page in doc)
    finally:
        doc.close()
    avg = total_chars / page_count if page_count else 0
    return page_count, avg < _SCANNED_CHARS_PER_PAGE
