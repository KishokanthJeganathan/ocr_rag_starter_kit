# generator/ — synthetic document generator

A fixture factory for the pipeline. Produces parameterised NDAs as PDFs, each
with a matching ground-truth JSON file. No network calls — text is templated, so
output is deterministic for a given `--seed`.

It is *not* the product and *not* wired into the pipeline. It writes files to a
folder; Stage 2 (ingestion) is what picks them up.

## Usage

```bash
cd generator
uv sync

# 5 random NDAs
uv run python -m generator make --type nda --count 5 --out ../fixtures

# a one-way NDA with a date-ordering defect
uv run python -m generator make --kind one-way --violation date_order --out ../fixtures

# a degraded, image-only "scanned" PDF (forces the OCR path)
uv run python -m generator make --scanned --seed 42 --out ../fixtures
```

Each run writes `<doc_id>.pdf` and `<doc_id>.gt.json` (the ground truth).

## Knobs

| Flag | Values | Effect |
|------|--------|--------|
| `--type` | `nda` | Document type (only NDA for now). |
| `--count` | int | How many to generate; seed increments per document. |
| `--kind` | `one-way` \| `mutual` \| `random` | NDA direction. |
| `--violation` | `date_order`, `missing_party_sig`, `missing_governing_law` | Inject a defect (repeatable). |
| `--scanned` | flag | Rasterise + skew + noise + JPEG; strip the text layer. |
| `--seed` | int | Base seed for reproducibility. |
| `--out` | path | Output directory (default `fixtures/`). |

## Injected violations

| Name | What it does | Rule it trips in Stage 6 |
|------|--------------|--------------------------|
| `date_order` | Term clause prints an expiry date before the effective date. | date ordering |
| `missing_party_sig` | A party named in the preamble has no signature block. | party consistency |
| `missing_governing_law` | The governing-law section is omitted. | required-clause present |

## Ground-truth sidecar

`<doc_id>.gt.json` records what is *true* about the document (parties, dates,
term, governing law, signatories) plus `injected_violations` and
`violation_details`. This is the generator's own record — it will inform, but
does not define, the Stage 4 extraction schema.
