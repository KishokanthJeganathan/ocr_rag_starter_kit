"""Document classification.

After OCR, take the first page's text and ask an LLM what kind of document this
is (NDA, invoice, or other) with a confidence score. The LLM is pinned to a
JSON shape via ``response_format`` — the SDK validates the reply into
``Classification`` for us, so there is no hand-rolled parsing here.

Best-effort by design: the worker treats a failure in here as "unknown" rather
than a pipeline error, because OCR has already succeeded by this point.
"""

from __future__ import annotations

from openai import OpenAI
from pydantic import BaseModel, Field

from app.config import settings
from app.models.enums import DocumentType
from app.services.ocr import OcrLayout

# How much of page 1 to send. A title plus a few clauses is plenty to tell an
# NDA from an invoice, and it keeps the call cheap.
_MAX_CHARS = 1500

_SYSTEM_PROMPT = (
    "You classify business and legal documents. Given the text extracted from a "
    "document's first page, decide whether it is a non-disclosure agreement "
    "('nda'), an invoice ('invoice'), or anything else ('other'). Give your "
    "confidence as a number from 0 to 1, and one short sentence of rationale."
)


class Classification(BaseModel):
    doc_type: DocumentType
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str


def _client() -> OpenAI:
    return OpenAI(api_key=settings.openai_api_key)


def _first_page_text(layout: OcrLayout) -> str:
    if not layout.pages:
        return ""
    text = "\n".join(block.text for block in layout.pages[0].blocks if block.text)
    return text[:_MAX_CHARS]


def classify_document(layout: OcrLayout) -> Classification:
    """Blocking call — run it via ``run_in_threadpool`` from async code."""
    completion = _client().chat.completions.parse(
        model=settings.classifier_model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _first_page_text(layout) or "(no text extracted)"},
        ],
        response_format=Classification,
    )
    parsed = completion.choices[0].message.parsed
    if parsed is None:
        raise RuntimeError("classifier returned no structured output")
    return parsed
