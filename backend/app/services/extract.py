"""Structured extraction.

Given the OCR layout of a document we have a schema for (NDA today), pull the
fields out with an LLM. Every field comes back wrapped as
``{value, confidence, evidence}`` — ``value`` is ``null`` when the field is
absent, ``evidence`` is the verbatim quote it was read from (``null`` when the
model inferred it). The wrapper is what the validation step and the review UI
work against.

Same mechanics as ``classify.py``: a Pydantic model is handed to the SDK as
``response_format``, which pins the reply to that JSON shape.
"""

from __future__ import annotations

from openai import OpenAI
from pydantic import BaseModel, Field

from app.config import settings
from app.services.ocr import OcrLayout

# NDAs are short; the whole document text fits in one call with room to spare.
_MAX_CHARS = 12_000


class Extracted[T](BaseModel):
    value: T | None
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str | None


class Party(BaseModel):
    name: str | None
    entity_type: str | None  # "corporation" | "llc" | "limited_partnership"
    incorporation_state: str | None


class Signatory(BaseModel):
    party: str | None
    name: str | None
    title: str | None


class NdaExtraction(BaseModel):
    agreement_type: Extracted[str]  # "one_way" | "mutual"
    disclosing_party: Extracted[Party]
    receiving_party: Extracted[Party]
    effective_date: Extracted[str]  # ISO date, YYYY-MM-DD
    expiry_date: Extracted[str]  # ISO date the term clause says the NDA expires
    term_years: Extracted[int]
    survival_years: Extracted[int]
    governing_law: Extracted[str]
    has_non_compete: Extracted[bool]
    non_compete_months: Extracted[int]
    signatories: Extracted[list[Signatory]]


_SYSTEM_PROMPT = (
    "You extract fields from a non-disclosure agreement. Use only what the text "
    "supports. For every field give: value (or null if the document does not "
    "state it), confidence 0..1, and evidence (the shortest verbatim quote you "
    "took it from, or null if you inferred it). Dates must be ISO YYYY-MM-DD. "
    "expiry_date is the termination/expiry date the term clause actually states, "
    "copied as written even if it looks wrong. agreement_type is 'one_way' or "
    "'mutual'. entity_type is 'corporation', 'llc', or 'limited_partnership'."
)


def _client() -> OpenAI:
    return OpenAI(api_key=settings.openai_api_key)


def _document_text(layout: OcrLayout) -> str:
    lines: list[str] = []
    for page in layout.pages:
        lines.append(f"--- page {page.number} ---")
        lines.extend(block.text for block in page.blocks if block.text)
    return "\n".join(lines)[:_MAX_CHARS]


def extract_nda(layout: OcrLayout) -> NdaExtraction:
    """Blocking call — run it via ``run_in_threadpool`` from async code."""
    completion = _client().chat.completions.parse(
        model=settings.extractor_model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _document_text(layout) or "(no text extracted)"},
        ],
        response_format=NdaExtraction,
    )
    parsed = completion.choices[0].message.parsed
    if parsed is None:
        raise RuntimeError("extractor returned no structured output")
    return parsed
