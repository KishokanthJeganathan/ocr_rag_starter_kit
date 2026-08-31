"""The defects the generator can deliberately inject into a document.

Each one is designed to trip a specific validation rule in Stage 6. The
ground-truth sidecar records which were injected so the eval harness can check
the pipeline caught them.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

# Term clause states an expiry date earlier than the effective date.
DATE_ORDER = "date_order"

# A party named in the preamble is absent from the signature blocks.
MISSING_PARTY_SIG = "missing_party_sig"

# The governing-law section is dropped entirely.
MISSING_GOVERNING_LAW = "missing_governing_law"

VALID_VIOLATIONS: frozenset[str] = frozenset({DATE_ORDER, MISSING_PARTY_SIG, MISSING_GOVERNING_LAW})


def normalise(values: Iterable[str] | None) -> tuple[str, ...]:
    """De-duplicate, order deterministically, and reject unknown names."""
    if not values:
        return ()
    seen = sorted({v.strip() for v in values if v.strip()})
    unknown = [v for v in seen if v not in VALID_VIOLATIONS]
    if unknown:
        raise ValueError(
            f"unknown violation(s): {', '.join(unknown)}; "
            f"valid: {', '.join(sorted(VALID_VIOLATIONS))}"
        )
    return tuple(seen)


def has(violations: Sequence[str], name: str) -> bool:
    return name in violations
