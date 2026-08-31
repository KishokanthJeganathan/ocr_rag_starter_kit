"""Validation rules — pure, no IO."""

from __future__ import annotations

from app.services.extract import Extracted, NdaExtraction, Party, Signatory
from app.services.validate import Verdict, validate_nda


def _clean() -> NdaExtraction:
    """An extraction that passes every rule with confidence to spare."""

    def cell(value: object) -> Extracted:
        return Extracted(value=value, confidence=0.95, evidence="…")

    return NdaExtraction(
        agreement_type=cell("mutual"),
        disclosing_party=cell(
            Party(name="A LLC", entity_type="llc", incorporation_state="Delaware")
        ),
        receiving_party=cell(Party(name="B LLC", entity_type="llc", incorporation_state="Florida")),
        effective_date=cell("2026-01-01"),
        expiry_date=cell("2029-01-01"),
        term_years=cell(3),
        survival_years=cell(5),
        governing_law=cell("Massachusetts"),
        has_non_compete=cell(False),
        non_compete_months=cell(None),
        signatories=cell(
            [
                Signatory(party="A LLC", name="Lisa", title="CEO"),
                Signatory(party="B LLC", name="Sam", title="GC"),
            ]
        ),
    )


def test_clean_extraction_passes() -> None:
    result = validate_nda(_clean())
    assert result.verdict is Verdict.PASSED
    assert result.issues == []


def test_missing_governing_law_is_an_error() -> None:
    x = _clean()
    x.governing_law = Extracted(value=None, confidence=0.95, evidence=None)

    result = validate_nda(x)

    assert result.verdict is Verdict.NEEDS_REVIEW
    assert [i.rule for i in result.issues] == ["governing_law_present"]
    assert result.issues[0].severity == "error"


def test_party_without_a_signature_block_is_an_error() -> None:
    x = _clean()
    x.signatories = Extracted(
        value=[Signatory(party="A LLC", name="Lisa", title="CEO")], confidence=0.95, evidence=None
    )

    result = validate_nda(x)

    assert any(
        i.rule == "signatory_per_party" and i.field == "receiving_party" for i in result.issues
    )


def test_expiry_before_effective_is_an_error() -> None:
    x = _clean()
    x.expiry_date = Extracted(value="2020-01-01", confidence=0.95, evidence="…")

    result = validate_nda(x)

    assert any(i.rule == "date_order" for i in result.issues)


def test_low_confidence_field_forces_review() -> None:
    x = _clean()
    x.survival_years = Extracted(value=5, confidence=0.4, evidence="…")

    result = validate_nda(x)

    assert result.verdict is Verdict.NEEDS_REVIEW
    issue = next(i for i in result.issues if i.field == "survival_years")
    assert issue.rule == "confidence"
    assert issue.severity == "warning"
