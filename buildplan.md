Phase A — Foundations
Stage 0 — Repo + infra skeleton
Build: Monorepo (backend/, frontend/, generator/, evals/, infra/). uv + ruff + mypy + pytest + pre-commit. Docker Compose: postgres (pgvector image), redis, minio, api, worker, web. FastAPI app with GET /health. pydantic-settings config. SQLAlchemy 2.0 + Alembic; migration 001: tenants, matters, documents (status enum), audit_log. RLS policies on tenant-scoped tables + SET app.current_tenant dependency. GitHub Actions: lint + type + test against a Postgres service.
Done when: docker compose up boots all services, /health green, CI green, a test proves RLS blocks cross-tenant reads.

Stage 1 — Synthetic NDA generator (fixture factory)
Build: generator/ — parameterized NDA builder: mutual/one-way, parties, jurisdiction, effective date, term length, survival period, non-compete present/absent, signature-block completeness. Render via WeasyPrint (HTML/CSS → clean PDF). --violation flag: date_order, missing_party_sig, missing_governing_law. --scanned mode: rasterize + skew + gaussian noise + JPEG recompress. Emits a ground-truth JSON sidecar per document. CLI: python -m generator make --type nda --one-way --violation date_order --scanned --out ./fixtures.
Done when: one command produces N NDAs + ground truth; clean and scanned variants both open; injected violations are present in the text.

Do this early — every downstream stage needs inputs.

Phase B — Ingestion pipeline
Stage 2 — Ingestion service
Build: POST /v1/documents (multipart: file, matter_id). MIME sniff with python-magic; accept PDF/PNG/JPG/DOCX. Digital-vs-scanned detection (PyMuPDF text-chars-per-page heuristic). SHA-256 → dedup + S3/MinIO key. documents row status=QUEUED; enqueue ARQ job. Worker skeleton + processing_events status trail. Audit writes.
Done when: upload a generated PDF → row created, file in MinIO, job queued, re-uploading the same bytes is deduped, DOCX is accepted.

Stage 3 — OCR & layout layer
Build: OCREngine protocol → analyze(bytes) -> LayoutDocument. Azure Document Intelligence adapter (prebuilt-layout). Normalized model: Document → Page → Block(text, bbox_normalized, confidence, role), persisted as JSONB on the document. Cache per-page PNGs to S3 for the review UI. Leave a PaddleOCREngine stub class (seam only).
Done when: worker runs OCR on an uploaded doc, layout JSONB is persisted with page/bbox/confidence, page images are retrievable.

Stage 4 — Classification + schema registry
Build: Registry: schemas/nda/v1.py (Pydantic), schema_versions table, lookup by (doc_type, version). Claude (claude-sonnet-5) classification over first ~2 pages of layout markdown → {doc_type, confidence}. Binding + gate: confidence < 0.85 or no registered schema → status=UNRECOGNIZED → review, pipeline stops.
Done when: generated NDA → nda@v1, confidence logged; a non-NDA fixture → UNRECOGNIZED.

Stage 5 — Structured extraction
Build: Anthropic SDK, structured outputs (output_config.format) against NDAExtraction — every field is {value, source_text, page, bbox, confidence}. Prompt caching (system + schema + few-shot + layout block). Retry-on-validation-failure loop, max 2, re-prompt with the error. Grounding map: string-match source_text into the layout to recover bbox. Persist extraction_result JSONB + extraction_version.
Done when: NDA → structured fields with page + bbox provenance, visible at GET /v1/documents/{id}; usage.cache_read_input_tokens > 0 on the second run.

Stage 6 — Validation funnel
Build: Tiered engine. Tier 0 ingestion sanity (OCR produced text, confidence distribution, page count). Tier 2 Pydantic structural (required/types/enums/formats). Tier 3 grounding (source span exists, value derivable, bbox resolves, no invented fields — schema-independent). Tier 4 business rules from the registry: nda.dates_ordered, nda.parties_distinct, nda.parties_in_signature_block, nda.effective_not_future. Confidence-gating config (per-field/per-doc thresholds). Write validation_results rows; set status = NEEDS_REVIEW on any ERROR, else READY_FOR_REVIEW.
Done when: clean NDA passes all tiers; --violation date_order NDA → NEEDS_REVIEW with termination_date flagged by nda.dates_ordered.

Phase C — Human in the loop
Stage 7 — Review interface
Build: Next.js + TS + shadcn/ui + Tailwind + TanStack Query. Queue list (status filter). Document detail: page image with absolute-positioned bbox overlays + field panel. Click field → highlight its box. Edit value + reason → PATCH /v1/documents/{id}/fields/{name} → append-only field_corrections row → re-run validation. Approve (enabled at 0 errors) → approved_snapshots row (canonical-JSON SHA-256, schema_version, supersedes chain), status=APPROVED, DB trigger locks extraction writes. Audit-trail panel reading audit_log. Auth: NextAuth, single demo user.
Done when: the full broken-NDA walkthrough runs end to end — flag → correct one field → approve → locked snapshot → audit trail shows every event.

Stage 8 — Export API
Build: GET /v1/documents/{id}/export?format=json|csv — serves only the latest approved snapshot; 409 if not approved. API-key auth for this endpoint (separate from UI session). Audit exported.
Done when: approved NDA exports as JSON and CSV; non-approved returns 409; export is audited.

Phase D — RAG
Stage 9 — RAG question answering
Build: Layout-aware chunker (split on section/paragraph, carry page + bbox + doc_id). chunks table + pgvector column, HNSW index. Embeddings: Voyage voyage-3-large (swap to voyage-law-2 behind config), embed on approval. Hybrid retrieval: pgvector dense + Postgres tsvector/ts_rank, combined with Reciprocal Rank Fusion. Rerank: Voyage rerank-2.5. POST /v1/chat streamed SSE, claude-sonnet-5, answer + citations (doc name + page). Relevance floor on reranked chunks → explicit "not found," enforced in prompt and code. Frontend chat panel: streaming, citation chips that jump to the cited page.
Done when: ask "what's the survival period?" → cited answer; ask about a clause the generator omitted → "not found."

Phase E — Rigor + ship
Stage 10 — Golden evals + CI gate
Build: evals/ runner: run the pipeline over the generated golden set + ~10 real SEC EDGAR agreements, diff against ground truth. Field-level precision/recall/F1 (exact + normalized), classification confusion matrix. RAG eval: Ragas (faithfulness, context precision/recall) + retrieval hit@k on a Q→(doc,page) key. Commit a baseline metrics file. CI job on PRs touching prompts/** or schemas/**: fail if F1 drops > 3% below baseline. Wire Langfuse for traces + cost.
Done when: make eval produces the report; the CI gate fails a deliberately worsened prompt; baseline is committed.

Stage 11 — AWS deploy
Build: Terraform: VPC, ECS Fargate (api + worker services), RDS Postgres with pgvector, ElastiCache Redis, S3, ALB, ECR, Secrets Manager. GitHub Actions: build → push ECR → migrate (one-off task) → deploy. structlog → CloudWatch; Sentry (API + web); CloudWatch alarms → SNS email.
Done when: a public URL runs the whole demo; a pushed commit deploys automatically; an induced error shows in Sentry.

Stage 12 — Demo polish
Build: Landing = the pipeline/queue view; generator demoted to a secondary "Add test document" action. Seed script: a spread of NDAs (clean, each violation type, scanned). Written demo script (the 5-beat narrative). README + architecture doc + pipeline diagram.
Done when: a cold visitor can run the full story in ~3 minutes without guidance.

Execution notes
Critical path: 0 → 2 → 3 → 4 → 5 → 6 → 7. Stage 1 runs alongside 0. Stage 7 (frontend) can start scaffolding after Stage 4. Stages 10–11 can begin once Stage 7 works.
Thin stages: 8 and 12 are small. 7 and 9 are the heavy ones.
Invoice as second type: deferred. Slots in as "Stage 5b/6b" (new schema + rules) after Stage 9 if you want the contrast for the demo — ~2 days, no architecture change.
First milestone worth stopping at: end of Stage 7 — that's the complete extraction + review + approval story, demoable without RAG.
