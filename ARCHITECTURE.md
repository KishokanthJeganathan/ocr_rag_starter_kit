# Architecture

What's in the tree today, and how a request flows through it. Scope: **upload a
document → OCR it → classify it → (if NDA) extract its fields → validate them →
chunk + embed for retrieval → view it all, and ask questions across the corpus,
in a read-only UI.** An editable review workflow is not here yet.

## Moving parts

| Process | What it is | Code |
|---|---|---|
| **api** | FastAPI HTTP service | `backend/app/main.py`, `backend/app/api/` |
| **worker** | ARQ background worker (one process, pulls jobs from Redis) | `backend/app/worker.py` |
| **web** | Next.js read-only review UI (runs on the host, not in Compose) | `web/app/` |
| **Postgres** | metadata: tenants, matters, documents, OCR layouts | `backend/app/models/`, `backend/alembic/` |
| **Redis** | the job queue between api and worker | `backend/app/queue.py` |
| **MinIO / S3** | the original file bytes + rasterized page PNGs | `backend/app/services/storage.py` |
| **generator** | makes synthetic NDA PDFs — used by the CLI *and* imported by the api (`POST /v1/documents/synthetic`) | `generator/` (its own package, editable path dep) |

## The journey of one upload

```
  POST /v1/documents            (file + matter_id, header X-Tenant-Id)
  POST /v1/documents/synthetic  (NDA params → generator builds the PDF, then same path)
        │
        ▼  api/documents.py : upload_document() / create_synthetic_document()
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
  │ classify.classify_document   page-1 text -> OpenAI ->        │
  │                              doc_type + confidence (best-effort)│
  │ extract.extract_nda          if NDA: full text -> OpenAI ->  │
  │                              fields{value,confidence,evidence}│
  │ validate.validate_nda        rules + confidence gate ->      │
  │                              verdict + issues (pure code)    │
  │ chunk.chunk_layout           text -> LangChain splitter ->   │
  │                              overlapping ~500-token windows  │
  │ embed.embed_texts            each window -> vector (LangChain)│
  │ INSERT document_layouts      (normalized JSON)              │
  │ INSERT document_chunks       (text + embedding, per window) │
  │ INSERT document_extractions  (if NDA)                       │
  │ INSERT document_validations  (if NDA)                       │
  │ UPDATE documents             doc_type, confidence,          │
  │                              status -> processed            │
  │  … on an OCR error: status -> failed, error = "…"          │
  └─────────────────────────────────────────────────────────────┘

  GET  /v1/documents/{id}/layout        -> the normalized layout JSON
  GET  /v1/documents/{id}/extraction    -> the extracted fields (NDA only)
  GET  /v1/documents/{id}/validation    -> verdict + issues (NDA only)
  GET  /v1/documents/{id}/pages/{n}.png -> the rasterized page image (from S3)
  GET  /v1/documents/{id}               -> the document row (status, doc_type, ...)
  GET  /v1/documents                    -> this tenant's documents
  POST /v1/ask   {question, document_id?}  -> embed q -> pgvector nearest chunks
                                              -> LLM answer + [S1] sources
                                              (each: filename, page, distance,
                                               and the full chunk text sent to the LLM)
```

## Every file

**HTTP layer**
| File | Role |
|---|---|
| `app/main.py` | builds the FastAPI app, wires the routers, opens/closes the Redis pool |
| `app/api/documents.py` | upload, synthetic, list, get, layout, extraction, validation, page image |
| `app/api/ask.py` | `POST /v1/ask` — RAG Q&A over `document_chunks` |
| `app/deps.py` | `X-Tenant-Id` header → tenant-scoped DB session (stopgap until real auth) |
| `app/schemas.py` | Pydantic request/response shapes (`DocumentOut`, `UploadResult`) |
| `app/config.py` | settings from env / repo-root `.env` |

**Pipeline logic** (`app/services/`)
| File | Role |
|---|---|
| `ingest.py` | the upload flow: detect → hash → dedup → check matter → store → insert row |
| `synthesize.py` | maps a `SyntheticNdaRequest` → `generator.params.build_nda` → PDF bytes |
| `detect.py` | file type (python-magic) + scanned-vs-digital + page count (PyMuPDF) |
| `storage.py` | thin boto3 wrapper — `upload_bytes` / `download_bytes` (MinIO or S3) |
| `ocr.py` | `rasterize` (pages → PNG) + `analyze_pages` (Textract → normalized `OcrLayout`) |
| `classify.py` | page-1 text → OpenAI → `Classification` (`doc_type`, `confidence`, `rationale`) |
| `extract.py` | NDA text → OpenAI → `NdaExtraction` (each field `{value, confidence, evidence}`) |
| `validate.py` | rules + confidence gate over `NdaExtraction` → `Validation` (`verdict`, `issues`). Pure. |
| `chunk.py` | layout dict → overlapping `Chunk`s via LangChain `RecursiveCharacterTextSplitter` (~256 tokens); skips header/footer/page-number blocks; page tracked by forward-only offset lookup. Pure. |
| `embed.py` | text → vectors via LangChain `OpenAIEmbeddings` (`text-embedding-3-small`) |
| `retrieve.py` | pgvector cosine-nearest `document_chunks` (RLS-scoped, optional one-doc filter, drops matches past `retrieval_max_distance`) |
| `answer.py` | retrieved chunks + question → OpenAI → grounded answer + `Source[]` |

**Worker**
| File | Role |
|---|---|
| `app/worker.py` | `process_document` = OCR + classify + (NDA) extract + validate + chunk/embed; `WorkerSettings` registers it |
| `app/queue.py` | the Redis connection the api uses to enqueue jobs |

**Data**
| File | Role |
|---|---|
| `app/db.py` | async engine, session factory, `set_current_tenant` (the RLS switch) |
| `app/models/tenant.py` `matter.py` | the isolation hierarchy: tenant → matter |
| `app/models/document.py` | one uploaded file + its ingest/OCR status |
| `app/models/layout.py` | `document_layouts` — the OCR result, one row per document |
| `app/models/extraction.py` | `document_extractions` — the extracted fields, one row per NDA |
| `app/models/validation.py` | `document_validations` — the verdict + issues, one row per NDA |
| `app/models/chunk.py` | `document_chunks` — one retrievable passage + its `vector(1536)` embedding |
| `app/models/enums.py` | `SourceFormat`, `DocumentStatus`, `DocumentType` |
| `app/models/base.py` | declarative base + `created_at`/`updated_at` mixin |
| `alembic/versions/0001…0007` | migrations: tenants/matters, documents, layouts, classification, extractions, validations, chunks |

**Support**
| File | Role |
|---|---|
| `app/logging.py` | structlog JSON logging |
| `scripts/seed.py` | create the demo tenant + matter (`make seed`) |
| `scripts/try-ocr.sh` | upload a fixture, wait, print the layout (`make try-ocr`) |
| `tests/` | `test_rls`, `test_detect`, `test_ocr`, `test_classify`, `test_extract`, `test_validate`, `test_chunk`, `test_documents_api`, `test_ask_api`, `test_synthesize`, `test_health` |

**Review UI** (`web/`, Next.js App Router, all Server Components — no client data layer)
| File | Role |
|---|---|
| `app/lib/api.ts` | typed `fetch` wrappers + response types, tenant/matter ids |
| `app/page.tsx` | document list with verdict badges + "New NDA" link |
| `app/new/page.tsx` + `actions.ts` | the generate form + its server action (`POST /synthetic` → redirect) |
| `app/ask/page.tsx` + `ask-box.tsx` + `actions.ts` | corpus Q&A page; `AskBox` (client) is reused on the detail page. Each answer lists the chunks sent to the model — expandable full text + cosine distance |
| `app/documents/[id]/page.tsx` | detail: Ask panel, then page images ∥ fields (value·confidence·evidence) + issues |
| `app/documents/[id]/auto-refresh.tsx` | client component — polls `router.refresh()` while a doc is in flight |
| `app/documents/[id]/pages/[page]/route.ts` | proxies the page PNG, adds the tenant header |
| `app/globals.css` | the whole stylesheet (no framework) |

## Data model

```
tenants ──1:n── matters ──1:n── documents ──1:1── document_layouts
                                          ├──1:1── document_extractions  (NDA only)
                                          ├──1:1── document_validations  (NDA only)
                                          └──1:n── document_chunks       (text + embedding)
```

- **tenants / matters** — every other table carries `tenant_id`; RLS filters on it.
- **documents** — `status` (queued → processing → processed / failed),
  `source_format`, `is_scanned`, `page_count`, `content_sha256` (unique per
  tenant), `storage_key`, `error`, `doc_type` (`nda`/`invoice`/`other`, nullable),
  `doc_type_confidence`.
- **document_layouts** — `engine`, `page_count`, `layout` JSONB:
  `{ pages: [ { number, width, height, image_key, blocks: [ { text, bbox, confidence, role } ] } ] }`.
- **document_extractions** — one row per NDA: `schema_version` (`nda.v1`), `model`,
  `fields` JSONB: `{ <field>: { value, confidence, evidence }, ... }`.
- **document_validations** — one row per NDA: `verdict` (`passed` / `needs_review`),
  `issues` JSONB: `[ { rule, severity, field, message }, ... ]`.
- **document_chunks** — many per document: `chunk_index`, `page`, `text`,
  `embedding vector(1536)` (HNSW cosine index). Written by the worker; re-chunked
  (delete + insert) on every reprocess.

## Deliberately not here yet

- **Hybrid retrieval (full-text + RRF), a rerank pass, streamed answers** — RAG
  follow-ups; today it's vector-only, non-streaming.
- **Field editing, corrections history, approval snapshots, audit log, export** —
  Phase 3. The `web/` UI today is read-only.
- **Real auth** — currently a trusted `X-Tenant-Id` header; the UI hard-codes the
  demo tenant.
