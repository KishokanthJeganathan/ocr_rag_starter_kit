"""Parameterised NDA build (used by the review UI)."""

from __future__ import annotations

from datetime import date

import pymupdf

from generator.params import build_nda, spec_from_params
from generator.violations import MISSING_GOVERNING_LAW


def _text(pdf: bytes) -> str:
    doc = pymupdf.open(stream=pdf, filetype="pdf")
    raw = "".join(page.get_text() for page in doc)
    doc.close()
    return " ".join(raw.split())


def test_overrides_land_in_the_document() -> None:
    pdf, gt = build_nda(
        seed=1,
        disclosing_party="Acme Widgets LLC",
        receiving_party="Globex Corporation",
        effective_date=date(2027, 3, 4),
        term_years=2,
        governing_law="New York",
    )
    text = _text(pdf)

    assert "Acme Widgets LLC" in text
    assert "Globex Corporation" in text
    assert "March 4, 2027" in text
    assert "New York" in text
    assert gt["expected"]["disclosing_party"]["name"] == "Acme Widgets LLC"
    assert gt["expected"]["term_years"] == 2


def test_unset_fields_fall_back_to_the_seeded_sample() -> None:
    spec = spec_from_params(seed=7)
    assert spec.disclosing_party.name
    assert spec.governing_law
    assert spec.term_years in (2, 3, 5)


def test_injected_violation_is_reflected_in_ground_truth() -> None:
    _, gt = build_nda(seed=3, violations=(MISSING_GOVERNING_LAW,))
    assert gt["expected"]["governing_law"] is None
    assert MISSING_GOVERNING_LAW in gt["injected_violations"]


def test_signatories_follow_renamed_parties() -> None:
    spec = spec_from_params(seed=2, disclosing_party="A Co", receiving_party="B Co")
    parties = {s.party_name for s in spec.signatories}
    assert parties == {"A Co", "B Co"}
