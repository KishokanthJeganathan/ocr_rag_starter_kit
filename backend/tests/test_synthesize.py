"""Synthetic NDA builder — the adapter over the generator package."""

from __future__ import annotations

import datetime as dt
import uuid

import pytest

from app.schemas import SyntheticNdaRequest
from app.services.synthesize import build_synthetic_nda


def test_builds_a_real_pdf_with_the_overrides() -> None:
    req = SyntheticNdaRequest(
        matter_id=uuid.uuid4(),
        disclosing_party="Acme Widgets LLC",
        effective_date=dt.date(2027, 1, 1),
        term_years=2,
        agreement_type="mutual",
    )
    pdf = build_synthetic_nda(req)

    assert pdf[:5] == b"%PDF-"
    assert len(pdf) > 1000


def test_unknown_violation_raises_value_error() -> None:
    req = SyntheticNdaRequest(matter_id=uuid.uuid4(), violations=["bogus_defect"])
    with pytest.raises(ValueError):
        build_synthetic_nda(req)
