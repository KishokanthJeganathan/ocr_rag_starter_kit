"""Build a document from explicit parameters instead of purely from a seed.

The review UI calls this: the user fills in the fields they care about (party
names, dates, which defects to inject) and everything else is filled from a
random seed so each PDF is still unique. Nothing touches disk — the caller gets
PDF bytes and the ground-truth dict.
"""

from __future__ import annotations

import random
import tempfile
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

from generator.compose_nda import compose_nda
from generator.render_pdf import render_clean_pdf
from generator.sample import US_STATES, sample_nda_spec
from generator.spec import NdaSpec
from generator.violations import normalise

# Re-exported so callers (and the UI) share one list.
GOVERNING_LAW_CHOICES = tuple(US_STATES)


def spec_from_params(
    *,
    seed: int | None = None,
    kind: str = "random",
    disclosing_party: str | None = None,
    receiving_party: str | None = None,
    effective_date: date | None = None,
    term_years: int | None = None,
    governing_law: str | None = None,
    violations: tuple[str, ...] = (),
) -> NdaSpec:
    seed = random.randrange(1_000_000) if seed is None else seed
    spec = sample_nda_spec(
        seed=seed,
        doc_id=f"ui_{seed:06d}",
        kind=kind,
        injected_violations=normalise(violations),
    )

    disclosing = spec.disclosing_party
    receiving = spec.receiving_party
    if disclosing_party and disclosing_party.strip():
        disclosing = replace(disclosing, name=disclosing_party.strip())
    if receiving_party and receiving_party.strip():
        receiving = replace(receiving, name=receiving_party.strip())

    # Keep the signature blocks pointed at whatever the parties are now called.
    first, second = spec.signatories
    signatories = (
        replace(first, party_name=disclosing.name),
        replace(second, party_name=receiving.name),
    )

    return replace(
        spec,
        disclosing_party=disclosing,
        receiving_party=receiving,
        signatories=signatories,
        effective_date=effective_date or spec.effective_date,
        term_years=term_years or spec.term_years,
        governing_law=governing_law or spec.governing_law,
    )


def render_pdf_bytes(spec: NdaSpec) -> bytes:
    composed = compose_nda(spec)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / f"{spec.doc_id}.pdf"
        render_clean_pdf(composed, path)
        return path.read_bytes()


def build_nda(
    *,
    seed: int | None = None,
    kind: str = "random",
    disclosing_party: str | None = None,
    receiving_party: str | None = None,
    effective_date: date | None = None,
    term_years: int | None = None,
    governing_law: str | None = None,
    violations: tuple[str, ...] = (),
) -> tuple[bytes, dict[str, Any]]:
    """PDF bytes + the ground-truth dict, for a parameterised NDA."""
    resolved_seed = random.randrange(1_000_000) if seed is None else seed
    spec = spec_from_params(
        seed=resolved_seed,
        kind=kind,
        disclosing_party=disclosing_party,
        receiving_party=receiving_party,
        effective_date=effective_date,
        term_years=term_years,
        governing_law=governing_law,
        violations=violations,
    )
    ground_truth = spec.to_ground_truth(render_mode="clean", seed=resolved_seed)
    return render_pdf_bytes(spec), ground_truth
