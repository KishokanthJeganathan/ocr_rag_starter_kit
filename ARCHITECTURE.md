# Architecture

What's in the tree today, and how a request flows through it. Scope: **upload a
document → OCR it → read back the positioned text.** Nothing else exists yet.

## Moving parts

| Process | What it is | Code |
|---|---|---|
| **api** | FastAPI HTTP service | `backend/app/main.py`, `backend/app/api/` |
| **worker** | ARQ background worker (one process, pulls jobs from Redis) | `backend/app/worker.py` |
| **Postgres** | metadata: tenants, matters, documents, OCR layouts | `backend/app/models/`, `backend/alembic/` |
| **Redis** | the job queue between api and worker | `backend/app/queue.py` |
| **MinIO / S3** | the original file bytes + rasterized page PNGs | `backend/app/services/storage.py` |
| **generator** | standalone tool that makes synthetic NDA PDFs to test with | `generator/` (its own package) |

## The journey of one upload

```
  POST /v1/documents  (file + matter_id, header X-Tenant-Id)
        │
        ▼  api/documents.py : upload_document()
  ┌─────────────────────────────────────────────────────────────┐
  │ deps.py        X-Tenant-Id -> UUID -> a DB session with      │
  │                app.current_tenant set (RLS scopes every row) │
  │ services/ingest.py : ingest_document()                       │
  │   detect.py    magic bytes -> pdf/png/jpg/docx (else 415)    │
  │   hashlib      SHA-256 of the bytes                          │
  │   dedup        SELECT documents WHERE content_sha256 = …     │
  │                 -> if found, return it, duplicate=true       │
  │   check        the matter_id belongs to this tenant (else 404)│
  │   detect.py    if PDF: page_count + is_scanned (PyMuPDF)     │
  │   storage.py   upload_bytes -> {tenant}/{sha256}.pdf         │
  │   INSERT documents  (status = queued)                        │
  └─────────────────────────────────────────────────────────────┘
        │  session.commit()
        ▼  queue.py : enqueue_process_document(doc_id, tenant_id)
  ─────────────────────  Redis  ─────────────────────
        ▼  worker.py : process_document()
  ┌─────────────────────────────────────────────────────────────┐
  │ status -> processing                                        │
  │ storage.download_bytes(storage_key)                         │
  │ ocr.rasterize(data)          PDF pages -> PNG (PyMuPDF)      │
  │ ocr.analyze_pages(pages)     each PNG -> AWS Textract        │
  │                              LAYOUT blocks -> OcrLayout      │
  │ storage.upload_bytes(...)    a PNG per page                  │
  │ INSERT document_layouts      (normalized JSON)              │
  │  … on any error: status -> failed, error = "…"             │
  └─────────────────────────────────────────────────────────────┘

  GET /v1/documents/{id}/layout   -> the normalized layout JSON
  GET /v1/documents/{id}          -> the document row (status, page_count, error)
  GET /v1/documents               -> this tenant's documents
```

## Every file

**HTTP layer**
| File | Role |
|---|---|
| `app/main.py` | builds the FastAPI app, wires the router, opens/closes the Redis pool |
| `app/api/documents.py` | the 4 endpoints above |
| `app/deps.py` | `X-Tenant-Id` header → tenant-scoped DB session (stopgap until real auth) |
| `app/schemas.py` | Pydantic request/response shapes (`DocumentOut`, `UploadResult`) |
| `app/config.py` | settings from env / repo-root `.env` |

**Pipeline logic** (`app/services/`)
| File | Role |
|---|---|
| `ingest.py` | the upload flow: detect → hash → dedup → check matter → store → insert row |
| `detect.py` | file type (python-magic) + scanned-vs-digital + page count (PyMuPDF) |
| `storage.py` | thin boto3 wrapper — `upload_bytes` / `download_bytes` (MinIO or S3) |
| `ocr.py` | `rasterize` (pages → PNG) + `analyze_pages` (Textract → normalized `OcrLayout`) |

**Worker**
| File | Role |
|---|---|
| `app/worker.py` | `process_document` job = the OCR step; `WorkerSettings` registers it |
| `app/queue.py` | the Redis connection the api uses to enqueue jobs |

**Data**
| File | Role |
|---|---|
| `app/db.py` | async engine, session factory, `set_current_tenant` (the RLS switch) |
| `app/models/tenant.py` `matter.py` | the isolation hierarchy: tenant → matter |
| `app/models/document.py` | one uploaded file + its ingest/OCR status |
| `app/models/layout.py` | `document_layouts` — the OCR result, one row per document |
| `app/models/enums.py` | `SourceFormat`, `DocumentStatus` |
| `app/models/base.py` | declarative base + `created_at`/`updated_at` mixin |
| `alembic/versions/0001…0003` | the three migrations that build those tables + RLS |

**Support**
| File | Role |
|---|---|
| `app/logging.py` | structlog JSON logging |
| `scripts/seed.py` | create the demo tenant + matter (`make seed`) |
| `scripts/try-ocr.sh` | upload a fixture, wait, print the layout (`make try-ocr`) |
| `tests/` | `test_rls` (isolation), `test_detect`, `test_ocr`, `test_documents_api`, `test_health` |

## Data model

```
tenants ──1:n── matters ──1:n── documents ──1:1── document_layouts
```

- **tenants / matters** — every other table carries `tenant_id`; RLS filters on it.
- **documents** — `status` (queued → processing → failed), `source_format`,
  `is_scanned`, `page_count`, `content_sha256` (unique per tenant), `storage_key`,
  `error`.
- **document_layouts** — `engine`, `page_count`, `layout` JSONB:
  `{ pages: [ { number, width, height, image_key, blocks: [ { text, bbox, confidence, role } ] } ] }`.

## Deliberately not here yet

- **Classification, LLM extraction, validation** — the rest of Phase 1.
- **Chunking, embeddings, vector search, RAG** — Phase 2.
- **Review UI, corrections, approval snapshots, audit log, export** — Phase 3.
- **Real auth** — currently a trusted `X-Tenant-Id` header.
