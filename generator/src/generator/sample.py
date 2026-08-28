"""Build a random but reproducible :class:`NdaSpec` from an integer seed."""

from __future__ import annotations

import random
from datetime import date, timedelta

from faker import Faker

from generator import violations
from generator.spec import NdaSpec, Party, Signatory

US_STATES = [
    "Delaware",
    "New York",
    "California",
    "Texas",
    "Illinois",
    "Massachusetts",
    "Washington",
    "Florida",
]

ENTITY_TYPES = ["corporation", "llc", "limited_partnership"]

_ENTITY_SUFFIX = {
    "corporation": ", Inc.",
    "llc": " LLC",
    "limited_partnership": " L.P.",
}

_FAKER_SUFFIXES = (
    " Inc",
    " and Sons",
    " LLC",
    " Group",
    " PLC",
    " Ltd",
    ", Inc.",
    ", Ltd.",
)

TITLES = [
    "Chief Executive Officer",
    "General Counsel",
    "Chief Financial Officer",
    "VP, Business Development",
    "Head of Operations",
    "Authorized Signatory",
]

PURPOSES = [
    "a possible commercial partnership",
    "a potential acquisition of assets",
    "a technology licensing arrangement",
    "a joint product development effort",
    "a potential supply agreement",
]


def _strip_faker_suffix(name: str) -> str:
    for suffix in _FAKER_SUFFIXES:
        if name.endswith(suffix):
            return name[: -len(suffix)].rstrip(", ")
    return name.rstrip(", ")


def _make_party(fake: Faker, rng: random.Random) -> Party:
    entity_type = rng.choice(ENTITY_TYPES)
    base = _strip_faker_suffix(fake.company())
    return Party(
        name=f"{base}{_ENTITY_SUFFIX[entity_type]}",
        entity_type=entity_type,
        incorporation_state=rng.choice(US_STATES),
        address=fake.address().replace("\n", ", "),
    )


def sample_nda_spec(
    *,
    seed: int,
    doc_id: str,
    kind: str = "random",
    injected_violations: tuple[str, ...] = (),
) -> NdaSpec:
    rng = random.Random(seed)
    Faker.seed(seed)
    fake = Faker("en_US")

    if kind == "random":
        agreement_type = rng.choice(["one_way", "mutual"])
    else:
        agreement_type = {"one-way": "one_way", "mutual": "mutual"}[kind]

    disclosing = _make_party(fake, rng)
    receiving = _make_party(fake, rng)

    effective_date = date(2025, 1, 1) + timedelta(days=rng.randint(0, 730))
    has_non_compete = rng.random() < 0.4

    spec = NdaSpec(
        doc_id=doc_id,
        agreement_type=agreement_type,
        disclosing_party=disclosing,
        receiving_party=receiving,
        effective_date=effective_date,
        term_years=rng.choice([2, 3, 5]),
        survival_years=rng.choice([3, 5, 7]),
        governing_law=rng.choice(US_STATES),
        has_non_compete=has_non_compete,
        non_compete_months=rng.choice([12, 18, 24]) if has_non_compete else None,
        signatories=(
            Signatory(disclosing.name, fake.name(), rng.choice(TITLES)),
            Signatory(receiving.name, fake.name(), rng.choice(TITLES)),
        ),
        purpose=rng.choice(PURPOSES),
        injected_violations=violations.normalise(injected_violations),
    )
    return spec
