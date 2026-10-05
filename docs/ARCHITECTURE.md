# Architecture

```
Browser (Next.js 14, React, Tailwind, Recharts, MapLibre)
   │  same-origin /api/v1/*  (Next rewrite → API; no CORS in the browser)
   ▼
FastAPI  ── core: config · JWT/RBAC · audit · rate-limit · security headers · error envelope
   ├─ services/ingestion   validate → extract → metadata → chunk → embed → index → (review) → searchable
   ├─ services/retrieval   query analysis → BM25 ┐
   │                                   dense   ├→ filters → Reciprocal Rank Fusion → rerank → explainable hits
   ├─ services/rag         evidence selection → LLMProvider → citation validation → answer | evidence gap
   ├─ services/gis         layers (GeoJSON + joined values), region profile
   ├─ services/simulation  model registry → engine (pure functions) → sensitivity → provenance + hashes
   └─ providers            LLMProvider · EmbeddingProvider · ObjectStore · job runner
SQLite (dev/test) | PostgreSQL+PostGIS (compose)        Celery+Redis (optional) | FastAPI BackgroundTasks (default)
```

## Key design decisions

| Decision | Why |
|---|---|
| **Search behind an abstraction**, `local` backend (BM25 + cosine in-process over DB-stored chunks) | Runs everywhere (SQLite & Postgres), zero infra for a student team, fully explainable. Swap for OpenSearch/pgvector by implementing the same `search_evidence` contract. **Not** built for millions of chunks: the snapshot lives in process memory (fine at demo scale, ≈ tens of thousands of chunks). |
| **Hashing embeddings + domain lexicon** as the default `EmbeddingProvider` | Deterministic and offline. Honest limitation: lexical-ish with synonym concepts, *not* learned semantics. `EMBEDDING_PROVIDER=openai` gives true dense retrieval (re-ingest after switching). |
| **Extractive LLM provider** as default `LLMProvider` | Cannot hallucinate: it selects verbatim sentences. Anthropic/OpenAI providers use the same validation path. |
| **Citation validation is provider-independent** | Unknown evidence ids dropped; claim must overlap its cited passage; every number in a claim must appear in the cited passage. Tested against a hallucinating fake LLM. |
| **Prompt-injection posture** | Evidence is delimited, delimiter-like text is neutralised, instruction-like passages are *excluded from synthesis* but still shown (flagged); output is never executed; claims still need passage support. |
| **Role re-read from DB on every request** | A stale token never retains elevated privileges. Self-registration always yields `researcher`. |
| **Models are versioned, never mutated** | Editing coefficients creates a new version and deprecates the old; every run stores model version + input/output hashes. |
| **Audit stores hashes, not query text** | Data minimisation; IP + truncated user-agent only. |
| **Schematic hex-tile geography** | No official boundary data available offline; honesty over false precision (see DATA_SOURCES). |

## Data flow for the demo
Question → `/search` + `/research/ask` (parallel) → cited claims → `GET /documents/{id}/chunks/{chunk}` for the exact passage → `/gis/layers` + `/regions/{id}` → `/models/{id}/baseline?region_id=` → `/scenarios` + `/run` → `/workspaces/{id}/items` → `/workspaces/{id}/brief`.

## Known limitations (deliberate scope)
Grants/Innovation portal and review-workflow collaboration (PRD P2) are not built. OIDC login, S3 adapter, OpenSearch/pgvector adapters, OCR for scanned PDFs, Hindi/multilingual retrieval, and streaming AI responses are roadmap items. Rate limiting is in-process (single node). JWT is held in `localStorage` (prototype trade-off; use httpOnly cookies + CSRF for production).
