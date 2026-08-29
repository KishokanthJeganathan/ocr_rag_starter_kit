# Document Intelligence pipeline

Ingest legal/business PDFs, extract structured data from them, answer questions
across them with page-level citations, with a human reviewer in the loop.

Built in three phases. **Only the current phase's code is in the tree** — review,
approvals, and RAG are added when we reach them, not before. See
[ARCHITECTURE.md](ARCHITECTURE.md) for how the current code fits together.

### Phase 1 — Extraction (in progress)

| Step | Status |
|---|---|
| Ingest an upload (detect, hash, dedup, store) | ✅ |
| OCR & layout (AWS Textract → positioned text blocks) | ✅ |
| Classify the document type (OpenAI → `nda` / `invoice` / `other` + confidence) | ✅ |
| LLM extraction — NDA fields as `{value, confidence, evidence}` against a schema | ✅ |
| Validation rules + confidence gating → `passed` / `needs_review` | ✅ |

### Phase 2 — RAG

Chunk the layout → embed → hybrid search + rerank → streamed answers with page
citations.

### Phase 3 — Review & approvals

Review UI, field corrections with history, locked approval snapshots, audit log,
export API.

*Cross-cutting, any time:* golden evals, AWS deploy.

## Layout

```
backend/     FastAPI API + ARQ worker, SQLAlchemy models, Alembic migrations
web/         Next.js read-only review UI (extraction + validation viewer)
generator/   Synthetic NDA generator (standalone package with its own venv)
infra/       Postgres bootstrap now; AWS Terraform later
```

## Generating test documents

```bash
cd generator && uv sync
uv run python -m generator make --type nda --count 5 --out ../fixtures
```

See [generator/README.md](generator/README.md) for all flags (`--kind`,
`--violation`, `--scanned`, `--seed`). `fixtures/` is git-ignored.

## Upload a document and see the OCR result

```bash
make seed                              # demo tenant + matter
make try-ocr F=fixtures/nda_02000.pdf  # upload, wait, print layout + extraction
```

The upload is sniffed (PDF/PNG/JPG/DOCX), hashed (SHA-256), deduplicated per
tenant, stored at `{tenant}/{sha256}.{ext}`, recorded in `documents`, and queued
to the worker. The worker then runs **OCR (AWS Textract)**: rasterize each page,
send it to `analyze_document` with the LAYOUT feature, and store the normalized
result (`pages → blocks → {text, bbox, confidence, role}`) in `document_layouts`,
plus a PNG per page. Read it back at `GET /v1/documents/{id}/layout`.

Then it **classifies** the document — the first page's text goes to OpenAI,
which returns `doc_type` (`nda` / `invoice` / `other`) + a confidence, stored on
the `documents` row.

If it's an NDA, it **extracts** the fields — the whole document text goes to
OpenAI against a Pydantic schema, and each field comes back as
`{value, confidence, evidence}` in `document_extractions`. Read it at
`GET /v1/documents/{id}/extraction`.

Then it **validates** — pure rules over the extracted fields (governing law
present, a signature block per party, expiry after effective date, required
fields) plus confidence gating (any field below `CONFIDENCE_THRESHOLD`). The
result is a verdict (`passed` / `needs_review`) and a list of issues in
`document_validations`, at `GET /v1/documents/{id}/validation`. `needs_review`
is what the Phase 3 review queue will pick up.

The document ends at `status = processed`. Classification and extraction are
best-effort: if an LLM call fails the document is still `processed` (OCR already
succeeded) — just without a `doc_type`, extraction, or validation row.

## Review UI

A **read-only** Next.js viewer for what the pipeline produced — a document list
with verdict badges, and a per-document page showing the scan next to the
extracted fields (value · confidence · evidence) with the failing fields
highlighted. Editing, approval, and corrections are Phase 3.

```bash
make web-install     # first time only
make web             # http://localhost:3100  (needs `make up` running)
```

It runs on the host (not in Compose) and talks to the API at
`http://localhost:8000` as the demo tenant. Config: `web/.env.local`.

## Configuration

Copy `.env.example` to `.env` at the repo root (git-ignored). Docker Compose and
the app both read it.

- **Local default:** `S3_ENDPOINT_URL=http://minio:9000` → storage is MinIO. OCR
  still calls real Textract, so set AWS credentials if you want the worker to
  succeed.
- **Full AWS:** blank `S3_ENDPOINT_URL`, then set `S3_BUCKET`, `S3_REGION`,
  `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`. The IAM user needs `s3:*` on the
  bucket and `textract:AnalyzeDocument`.
- **Classification:** set `OPENAI_API_KEY` (from
  [platform.openai.com](https://platform.openai.com), needs prepaid credits).
  Without it the worker still runs OCR; documents finish `processed` with a null
  `doc_type`.

## Quickstart (local)

Requires Docker, `uv`, and Python 3.12.

```bash
make up          # start postgres (pgvector), redis, minio, api, worker
make migrate     # apply database migrations
curl localhost:8000/health          # -> {"status":"ok",...}
curl localhost:8000/health/ready    # -> checks database + redis

make check       # ruff + mypy + pytest (runs against the running postgres)
```

Ports: API `8000`, review UI `3100` (host, `make web`), Postgres `5433` (host) →
`5432` (container), Redis `6379`, MinIO API `9000`, MinIO console `9001`
(`minioadmin` / `minioadmin`). Postgres is on `5433` so it doesn't collide with a
native install on `5432`.

## Foundations

- One-command local stack via Docker Compose (Postgres, Redis, MinIO, API, worker).
- FastAPI with `/health` and `/health/ready`; ARQ worker on Redis.
- **PostgreSQL row-level security**: the app connects as a non-superuser role with
  `FORCE ROW LEVEL SECURITY`; every tenant-scoped table is filtered by
  `current_setting('app.current_tenant')`. Tests prove cross-tenant reads and
  writes are blocked.
- Migrations: `0001` tenants + matters, `0002` documents, `0003` document_layouts.
- GitHub Actions CI: ruff, mypy, pytest.
