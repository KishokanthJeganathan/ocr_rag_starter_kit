# OCR-RAG Document Intelligence

A production-shaped pipeline for legal and business documents: ingest scanned or
digital PDFs, run OCR and layout extraction, extract structured data against a
versioned schema, validate it, route uncertain cases to a human reviewer, lock an
approved snapshot, and answer questions across documents with page-level
citations.

This repository is built **stage by stage**. Each stage ends with something that
runs and can be demonstrated.

| Stage | Title | Status |
|------:|-------|--------|
| 0 | Repo + infra skeleton | ✅ in progress |
| 1 | Synthetic NDA generator (fixture factory) | ⬜ |
| 2 | Ingestion service | ⬜ |
| 3 | OCR & layout layer | ⬜ |
| 4 | Classification + schema registry | ⬜ |
| 5 | Structured extraction | ⬜ |
| 6 | Validation funnel | ⬜ |
| 7 | Review interface | ⬜ |
| 8 | Export API | ⬜ |
| 9 | RAG question answering | ⬜ |
| 10 | Golden evals + CI gate | ⬜ |
| 11 | AWS deploy | ⬜ |
| 12 | Demo polish | ⬜ |

## Layout

```
backend/     FastAPI API + ARQ worker, SQLAlchemy models, Alembic migrations
frontend/    Review UI (Next.js) — added in Stage 7
generator/   Synthetic document generator — added in Stage 1
evals/       Golden-set evaluation harness — added in Stage 10
infra/       Terraform + local bootstrap — Postgres init script now, AWS in Stage 11
```

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

## What Stage 0 delivers

- One-command local stack via Docker Compose.
- FastAPI service with `/health` (liveness) and `/health/ready` (DB + Redis).
- ARQ worker skeleton wired to Redis.
- SQLAlchemy 2.0 models + Alembic migration `0001`: `tenants` and `matters` —
  the tenant isolation hierarchy only. `documents`, the audit log, and
  extraction-schema tables are added by the stages that first use them.
- **PostgreSQL row-level security**: the application connects as a non-superuser
  role with `FORCE ROW LEVEL SECURITY`; every tenant-scoped table is isolated by
  `current_setting('app.current_tenant')`. A test proves cross-tenant reads and
  writes are blocked.
- GitHub Actions CI: lint (ruff), type-check (mypy), tests (pytest against a
  Postgres + Redis service).
