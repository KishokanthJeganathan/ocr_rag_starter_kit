"""Extraction service — no network: the OpenAI client is faked."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import extract
from app.services.extract import Extracted, NdaExtraction, Party, Signatory
from app.services.ocr import OcrBlock, OcrLayout, OcrPage


def _layout(*pages: list[str]) -> OcrLayout:
    return OcrLayout(
        engine="textract",
        pages=[
            OcrPage(
                number=i,
                width=1000,
                height=1400,
                blocks=[
                    OcrBlock(text=t, bbox=(0.1, 0.1, 0.9, 0.2), confidence=0.99, role="text")
                    for t in texts
                ],
            )
            for i, texts in enumerate(pages, start=1)
        ],
    )


def _fake_client(parsed: object) -> SimpleNamespace:
    completions = SimpleNamespace(
        parse=lambda **kwargs: SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(parsed=parsed))]
        )
    )
    return SimpleNamespace(chat=SimpleNamespace(completions=completions))


def _sample() -> NdaExtraction:
    return NdaExtraction(
        agreement_type=Extracted(value="mutual", confidence=0.98, evidence="Mutual NDA"),
        disclosing_party=Extracted(
            value=Party(name="Chang-Fisher LLC", entity_type="llc", incorporation_state="Delaware"),
            confidence=0.95,
            evidence="Chang-Fisher LLC, a Delaware limited liability company",
        ),
        receiving_party=Extracted(
            value=Party(
                name="Kennedy-Garcia LLC", entity_type="llc", incorporation_state="Florida"
            ),
            confidence=0.93,
            evidence="Kennedy-Garcia LLC",
        ),
        effective_date=Extracted(value="2026-02-19", confidence=0.86, evidence="February 19, 2026"),
        expiry_date=Extracted(value="2029-02-19", confidence=0.8, evidence="February 19, 2029"),
        term_years=Extracted(value=3, confidence=0.9, evidence="three (3) years"),
        survival_years=Extracted(value=5, confidence=0.8, evidence="five (5) years"),
        governing_law=Extracted(value="Massachusetts", confidence=0.97, evidence="Massachusetts"),
        has_non_compete=Extracted(value=False, confidence=0.7, evidence=None),
        non_compete_months=Extracted(value=None, confidence=0.7, evidence=None),
        signatories=Extracted(
            value=[Signatory(party="Chang-Fisher LLC", name="Lisa Clayton", title="Head of Ops")],
            confidence=0.84,
            evidence="By: Lisa Clayton",
        ),
    )


def test_returns_the_parsed_extraction(monkeypatch: pytest.MonkeyPatch) -> None:
    want = _sample()
    monkeypatch.setattr(extract, "_client", lambda: _fake_client(want))

    got = extract.extract_nda(_layout(["NON-DISCLOSURE AGREEMENT"]))

    assert got.governing_law.value == "Massachusetts"
    assert got.term_years.value == 3
    assert got.non_compete_months.value is None


def test_raises_when_model_returns_no_structured_output(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(extract, "_client", lambda: _fake_client(None))

    with pytest.raises(RuntimeError):
        extract.extract_nda(_layout(["whatever"]))


def test_document_text_numbers_pages_and_truncates() -> None:
    text = extract._document_text(_layout(["a" * 20_000], ["page two"]))
    assert text.startswith("--- page 1 ---")
    assert len(text) == extract._MAX_CHARS
