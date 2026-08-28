"""Turn an :class:`NdaSpec` into the concrete text that gets rendered.

Templated prose with slots — no model calls. Violations that change *what is
written* (a bad expiry date, a dropped clause, a missing signature block) are
applied here; the ground truth in :mod:`generator.spec` still reflects what is
*true*.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from generator import violations
from generator.spec import NdaSpec, Signatory


def format_long_date(d: date) -> str:
    return f"{d:%B} {d.day}, {d.year}"


@dataclass(frozen=True)
class Section:
    heading: str
    body: str


@dataclass(frozen=True)
class ComposedNda:
    title: str
    frontmatter: list[str]
    sections: list[Section]
    closing: str
    signatories: list[Signatory]


def compose_nda(spec: NdaSpec) -> ComposedNda:
    mutual = spec.agreement_type == "mutual"
    disc, recv = spec.disclosing_party, spec.receiving_party
    quoted_a = "Party A" if mutual else "Discloser"
    quoted_b = "Party B" if mutual else "Recipient"
    obligations_subject = "Each party, as receiving party," if mutual else "The Recipient"

    title = "MUTUAL NON-DISCLOSURE AGREEMENT" if mutual else "NON-DISCLOSURE AGREEMENT"

    preamble = (
        f'This Non-Disclosure Agreement (this "Agreement") is entered into as of '
        f'{format_long_date(spec.effective_date)} (the "Effective Date") by and '
        f"between {disc.name}, a {disc.incorporation_state} {disc.entity_word} "
        f'("{quoted_a}"), and {recv.name}, a {recv.incorporation_state} '
        f'{recv.entity_word} ("{quoted_b}").'
    )
    recital = (
        f'The parties wish to explore {spec.purpose} (the "Purpose"), and '
        f"in connection with the Purpose one or both parties may disclose "
        f"confidential and proprietary information. NOW, THEREFORE, in "
        f"consideration of the mutual covenants in this Agreement, the parties "
        f"agree as follows:"
    )

    sections: list[Section] = [
        Section(
            "Definition of Confidential Information",
            '"Confidential Information" means all non-public information disclosed '
            "by one party to the other, whether orally, in writing, or by "
            "inspection of tangible objects, that is designated as confidential or "
            "that a reasonable person would understand to be confidential given "
            "its nature and the circumstances of disclosure.",
        ),
        Section(
            "Obligations",
            f"{obligations_subject} shall (a) hold the Confidential "
            "Information in strict confidence; (b) not disclose it to any third "
            "party without prior written consent; and (c) use it solely for the "
            "Purpose and for no other purpose.",
        ),
        Section(
            "Exclusions",
            "Confidential Information does not include information that (a) is or "
            "becomes publicly available through no fault of the receiving party; "
            "(b) was rightfully known to the receiving party before disclosure; "
            "(c) is independently developed without use of the Confidential "
            "Information; or (d) is rightfully obtained from a third party without "
            "restriction.",
        ),
        Section(
            "Term",
            f"This Agreement commences on the Effective Date and remains in effect "
            f"for {spec.term_years} years, expiring on "
            f"{format_long_date(spec.rendered_expiry())}, unless terminated "
            f"earlier by either party on thirty (30) days' written notice.",
        ),
        Section(
            "Survival",
            f"The confidentiality obligations in Sections 1 through 3 survive "
            f"termination or expiration of this Agreement for a period of "
            f"{spec.survival_years} years.",
        ),
    ]

    if spec.has_non_compete:
        sections.append(
            Section(
                "Non-Solicitation",
                f"For {spec.non_compete_months} months following the Effective "
                "Date, the Recipient shall not solicit for employment any employee "
                "of the Discloser with whom the Recipient had material contact in "
                "connection with the Purpose.",
            )
        )

    sections.append(
        Section(
            "Return of Materials",
            "Upon written request, the receiving party shall promptly return or "
            "destroy all materials embodying Confidential Information and, on "
            "request, certify such destruction in writing.",
        )
    )

    if not violations.has(spec.injected_violations, violations.MISSING_GOVERNING_LAW):
        sections.append(
            Section(
                "Governing Law",
                f"This Agreement is governed by the laws of the State of "
                f"{spec.governing_law}, without regard to its conflict-of-laws "
                f"principles.",
            )
        )

    sections.append(
        Section(
            "Miscellaneous",
            "This Agreement is the entire agreement between the parties regarding "
            "its subject matter and supersedes all prior discussions. It may be "
            "amended only by a writing signed by both parties. No waiver is "
            "effective unless in writing. If any provision is held unenforceable, "
            "the remaining provisions remain in full force.",
        )
    )

    closing = (
        "IN WITNESS WHEREOF, the parties have executed this Agreement as of the Effective Date."
    )

    signatories = list(spec.signatories)
    if violations.has(spec.injected_violations, violations.MISSING_PARTY_SIG):
        signatories = [s for s in signatories if s.party_name == spec.disclosing_party.name]

    return ComposedNda(
        title=title,
        frontmatter=[preamble, recital],
        sections=sections,
        closing=closing,
        signatories=signatories,
    )
