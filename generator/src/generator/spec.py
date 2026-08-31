"""The NDA specification — the set of facts that fully determines a generated
document. ``to_ground_truth`` serialises what is *true* about the document;
``ComposedNda`` (in compose_nda.py) is a separate view of what gets *rendered*.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from generator import violations

ENTITY_WORDS = {
    "corporation": "corporation",
    "llc": "limited liability company",
    "limited_partnership": "limited partnership",
}


def add_years(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year + years)
    except ValueError:  # Feb 29 in a non-leap target year
        return d.replace(year=d.year + years, day=28)


@dataclass(frozen=True)
class Party:
    name: str
    entity_type: str  # key of ENTITY_WORDS
    incorporation_state: str
    address: str

    @property
    def entity_word(self) -> str:
        return ENTITY_WORDS[self.entity_type]


@dataclass(frozen=True)
class Signatory:
    party_name: str
    name: str
    title: str


@dataclass(frozen=True)
class NdaSpec:
    doc_id: str
    agreement_type: str  # "one_way" | "mutual"
    disclosing_party: Party
    receiving_party: Party
    effective_date: date
    term_years: int
    survival_years: int
    governing_law: str
    has_non_compete: bool
    non_compete_months: int | None
    signatories: tuple[Signatory, ...]
    purpose: str
    injected_violations: tuple[str, ...] = ()

    # --- derived dates ---------------------------------------------------
    def correct_expiry(self) -> date:
        return add_years(self.effective_date, self.term_years)

    def rendered_expiry(self) -> date:
        """The expiry date actually printed. Under the ``date_order`` violation
        this is deliberately before the effective date."""
        if violations.has(self.injected_violations, violations.DATE_ORDER):
            return add_years(self.effective_date, -(self.term_years + 1))
        return self.correct_expiry()

    # --- ground truth --------------------------------------------------
    def to_ground_truth(self, *, render_mode: str, seed: int) -> dict[str, Any]:
        drops_law = violations.has(self.injected_violations, violations.MISSING_GOVERNING_LAW)
        detail: dict[str, Any] = {}
        if violations.has(self.injected_violations, violations.DATE_ORDER):
            detail[violations.DATE_ORDER] = {
                "rendered_expiry_date": self.rendered_expiry().isoformat(),
                "correct_expiry_date": self.correct_expiry().isoformat(),
            }
        if violations.has(self.injected_violations, violations.MISSING_PARTY_SIG):
            detail[violations.MISSING_PARTY_SIG] = {
                "party_missing_from_signatures": self.receiving_party.name,
            }

        return {
            "doc_id": self.doc_id,
            "doc_type": "nda",
            "render": {"mode": render_mode, "seed": seed},
            "expected": {
                "agreement_type": self.agreement_type,
                "disclosing_party": _party_gt(self.disclosing_party),
                "receiving_party": _party_gt(self.receiving_party),
                "effective_date": self.effective_date.isoformat(),
                "term_years": self.term_years,
                "survival_years": self.survival_years,
                "governing_law": None if drops_law else self.governing_law,
                "has_non_compete": self.has_non_compete,
                "non_compete_months": self.non_compete_months,
                "signatories": [
                    {"party": s.party_name, "name": s.name, "title": s.title}
                    for s in self.signatories
                ],
            },
            "injected_violations": list(self.injected_violations),
            "violation_details": detail,
        }


def _party_gt(p: Party) -> dict[str, str]:
    return {
        "name": p.name,
        "entity_type": p.entity_type,
        "incorporation_state": p.incorporation_state,
    }
