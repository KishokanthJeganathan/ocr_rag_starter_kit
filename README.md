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
| Classify the document type | ⬜ |
| LLM turns layout blocks into structured fields against a schema | ⬜ |
| Validation rules | ⬜ |

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
make try-ocr F=fixtures/nda_02000.pdf  # upload, wait for the worker, print the layout
```

The upload is sniffed (PDF/PNG/JPG/DOCX), hashed (SHA-256), deduplicated per
tenant, stored at `{tenant}/{sha256}.{ext}`, recorded in `documents`, and queued
to the worker. The worker then runs **OCR (AWS Textract)**: rasterize each page,
send it to `analyze_document` with the LAYOUT feature, and store the normalized
result (`pages → blocks → {text, bbox, confidence, role}`) in `document_layouts`,
plus a PNG per page. Read it back at `GET /v1/documents/{id}/layout`.

## Configuration

Copy `.env.example` to `.env` at the repo root (git-ignored). Docker Compose and
the app both read it.

- **Local default:** `S3_ENDPOINT_URL=http://minio:9000` → storage is MinIO. OCR
  still calls real Textract, so set AWS credentials if you want the worker to
  succeed.
- **Full AWS:** blank `S3_ENDPOINT_URL`, then set `S3_BUCKET`, `S3_REGION`,
  `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`. The IAM user needs `s3:*` on the
  bucket and `textract:AnalyzeDocument`.

## Quickstart (local)

Requires Docker, `uv`, and Python 3.12.

```bash
make up          # start postgres (pgvector), redis, minio, api, worker
make migrate     # apply database migrations
curl localhost:8000/health          # -> {"status":"ok",...}
curl localhost:8000/health/ready    # -> checks database + redis

make check       # ruff + mypy + pytest (runs against the running postgres)
```

Ports: API `8000`, Postgres `5433` (host) → `5432` (container), Redis `6379`,
MinIO API `9000`, MinIO console `9001` (`minioadmin` / `minioadmin`). Postgres is
on `5433` so it doesn't collide with a native install on `5432`.

## Foundations

- One-command local stack via Docker Compose (Postgres, Redis, MinIO, API, worker).
- FastAPI with `/health` and `/health/ready`; ARQ worker on Redis.
- **PostgreSQL row-level security**: the app connects as a non-superuser role with
  `FORCE ROW LEVEL SECURITY`; every tenant-scoped table is filtered by
  `current_setting('app.current_tenant')`. Tests prove cross-tenant reads and
  writes are blocked.
- Migrations: `0001` tenants + matters, `0002` documents, `0003` document_layouts.
- GitHub Actions CI: ruff, mypy, pytest.
