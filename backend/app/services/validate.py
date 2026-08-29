"""Validation rules for extracted NDA fields.

Pure and deterministic — no LLM, no IO. Takes an ``NdaExtraction`` and returns a
verdict plus the issues that formed it. ``needs_review`` is the signal the
review queue (Phase 3) will pick up.

Rules line up with the generator's injected violations (``date_order``,
``missing_party_sig``, ``missing_governing_law``) so the pipeline is measurable
against the ``.gt.json`` sidecars.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from enum import StrEnum

from pydantic import BaseModel

from app.config import settings
from app.services.extract import NdaExtraction


class Verdict(StrEnum):
    PASSED = "passed"
    NEEDS_REVIEW = "needs_review"


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


class Issue(BaseModel):
    rule: str
    severity: Severity
    field: str
    message: str


class Validation(BaseModel):
    verdict: Verdict
    issues: list[Issue]


def _as_date(value: str | None) -> dt.date | None:
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        return None


def _required_fields(x: NdaExtraction) -> list[Issue]:
    present = {
        "disclosing_party": bool(x.disclosing_party.value and x.disclosing_party.value.name),
        "receiving_party": bool(x.receiving_party.value and x.receiving_party.value.name),
        "effective_date": bool(x.effective_date.value),
    }
    return [
        Issue(
            rule="required_fields",
            severity=Severity.ERROR,
            field=field,
            message="missing from the document",
        )
        for field, ok in present.items()
        if not ok
    ]


def _governing_law_present(x: NdaExtraction) -> list[Issue]:
    if x.governing_law.value:
        return []
    return [
        Issue(
            rule="governing_law_present",
            severity=Severity.ERROR,
            field="governing_law",
            message="no governing-law clause found",
        )
    ]


def _signatory_per_party(x: NdaExtraction) -> list[Issue]:
    signed = {s.party for s in (x.signatories.value or []) if s.party}
    issues: list[Issue] = []
    for field in ("disclosing_party", "receiving_party"):
        party = getattr(x, field).value
        name = party.name if party else None
        if name and name not in signed:
            issues.append(
                Issue(
                    rule="signatory_per_party",
                    severity=Severity.ERROR,
                    field=field,
                    message=f"{name} has no signature block",
                )
            )
    return issues


def _date_order(x: NdaExtraction) -> list[Issue]:
    effective = _as_date(x.effective_date.value)
    expiry = _as_date(x.expiry_date.value)
    if effective and expiry and expiry <= effective:
        return [
            Issue(
                rule="date_order",
                severity=Severity.ERROR,
                field="expiry_date",
                message=f"expiry {expiry} is not after effective date {effective}",
            )
        ]
    return []


_RULES: tuple[Callable[[NdaExtraction], list[Issue]], ...] = (
    _required_fields,
    _governing_law_present,
    _signatory_per_party,
    _date_order,
)


def _low_confidence(x: NdaExtraction) -> list[Issue]:
    threshold = settings.confidence_threshold
    issues: list[Issue] = []
    for name in NdaExtraction.model_fields:
        confidence = getattr(x, name).confidence
        if confidence < threshold:
            issues.append(
                Issue(
                    rule="confidence",
                    severity=Severity.WARNING,
                    field=name,
                    message=f"confidence {confidence:.2f} below {threshold:.2f}",
                )
            )
    return issues


def validate_nda(extraction: NdaExtraction) -> Validation:
    issues: list[Issue] = []
    for rule in _RULES:
        issues.extend(rule(extraction))
    issues.extend(_low_confidence(extraction))
    verdict = Verdict.PASSED if not issues else Verdict.NEEDS_REVIEW
    return Validation(verdict=verdict, issues=issues)
