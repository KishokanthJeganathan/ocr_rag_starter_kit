"""Classification service — no network: the OpenAI client is faked."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.models.enums import DocumentType
from app.services import classify
from app.services.classify import Classification
from app.services.ocr import OcrBlock, OcrLayout, OcrPage


def _layout(*texts: str) -> OcrLayout:
    blocks = [
        OcrBlock(text=t, bbox=(0.1, 0.1, 0.9, 0.2), confidence=0.99, role="text") for t in texts
    ]
    return OcrLayout(
        engine="textract",
        pages=[OcrPage(number=1, width=1000, height=1400, blocks=blocks)],
    )


def _fake_client(parsed: object) -> SimpleNamespace:
    completions = SimpleNamespace(
        parse=lambda **kwargs: SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(parsed=parsed))]
        )
    )
    return SimpleNamespace(chat=SimpleNamespace(completions=completions))


def test_returns_the_parsed_classification(monkeypatch: pytest.MonkeyPatch) -> None:
    want = Classification(doc_type=DocumentType.NDA, confidence=0.97, rationale="mentions NDA")
    monkeypatch.setattr(classify, "_client", lambda: _fake_client(want))

    got = classify.classify_document(_layout("NON-DISCLOSURE AGREEMENT"))

    assert got.doc_type is DocumentType.NDA
    assert got.confidence == 0.97


def test_raises_when_model_returns_no_structured_output(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(classify, "_client", lambda: _fake_client(None))

    with pytest.raises(RuntimeError):
        classify.classify_document(_layout("whatever"))


def test_first_page_text_is_truncated() -> None:
    text = classify._first_page_text(_layout("x" * 5000))
    assert len(text) == classify._MAX_CHARS


def test_first_page_text_handles_empty_layout() -> None:
    assert classify._first_page_text(OcrLayout(engine="textract", pages=[])) == ""
