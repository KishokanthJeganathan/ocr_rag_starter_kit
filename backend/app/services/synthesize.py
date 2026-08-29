"""Build a synthetic NDA PDF from UI parameters.

Thin adapter over the standalone ``generator`` package — it owns what an NDA
looks like; this just maps the request and returns bytes.
"""

from __future__ import annotations

from typing import cast

from generator.params import build_nda

from app.schemas import SyntheticNdaRequest


def build_synthetic_nda(req: SyntheticNdaRequest) -> bytes:
    pdf, _ground_truth = build_nda(
        kind=req.agreement_type or "random",
        disclosing_party=req.disclosing_party,
        receiving_party=req.receiving_party,
        effective_date=req.effective_date,
        term_years=req.term_years,
        governing_law=req.governing_law,
        violations=tuple(req.violations),
    )
    return cast(bytes, pdf)
