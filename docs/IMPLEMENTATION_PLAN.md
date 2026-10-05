# SIH26019 — Implementation Plan

Platform: **National Digital Platform for Research, Policy Innovation, and Evidence-Based Land Governance**
Product spine (from the PRD): `Policy question → Evidence retrieval → Citation-grounded answer → GIS context → Scenario simulation → Comparison → Saved research`

## 1. PRD extraction summary

| Area | Extracted from PRD |
|---|---|
| Personas | Policy Researcher, Government Analyst, Domain Expert, Academic Researcher, Public User, Platform Admin |
| P0 modules | Evidence Repository, Hybrid Search + AI Researcher, Spatial Intelligence, Policy Scenario Lab, RBAC + audit |
| P1 | Workspace, sensitivity analysis, recommendations |
| P2 (deferred) | Grants/Innovation portal, advanced collaboration (comments/review workflows) |
| Entities | users, organizations, roles, documents, document_versions, document_chunks, topics, document_topics, regions, indicators, observations, models, scenarios, scenario_parameters, scenario_runs, workspaces, workspace_items, audit_events |
| APIs | `/api/v1/{search, research/ask, documents, regions, indicators, models, scenarios, workspaces, admin/*}` |
| Security | RBAC at API layer, audit, content hashes, prompt-injection isolation, provenance on exports |
| Demo | 12-step story: question → evidence → cited answer → passage → map → region → scenario → run → compare → save |

## 2. Ambiguities / contradictions and how they are resolved

| # | Issue | Decision |
|---|---|---|
| 1 | PRD says OpenSearch + vector index; brief allows pgvector; sandbox has neither | Search sits behind `SearchBackend`. Implemented backend: `local` (SQL-stored chunks, in-process BM25 + cosine). Works on SQLite and PostgreSQL. OpenSearch / pgvector adapters are documented extension points, **not implemented**. |
| 2 | Brief's dashboard shows "12,482 documents…" but also says "no placeholder dashboards" | Dashboard shows **real counts from the database**. |
| 3 | PRD wants 100–500 curated official documents; no network for official sources here | Seed corpus is **authored demo material, labelled DEMO**, never attributed to real agencies. Real PDFs go through the same ingestion pipeline (`data/documents/`, admin upload). |
| 4 | Embeddings: no API key in sandbox | `EmbeddingProvider` default = deterministic local **hashing embeddings** (lexical-ish, documented as *not* truly semantic). OpenAI provider available via env. |
| 5 | LLM: no API key in sandbox | `LLMProvider` default = **extractive** provider (selects supporting sentences; no generation). Anthropic and OpenAI providers via env. Citation validation is identical for all providers. |
| 6 | Role naming: PRD "Analyst/Official", "Expert/Reviewer" | Roles: `public` (anonymous), `researcher`, `analyst`, `expert`, `admin`. |
| 7 | PRD "OIDC/OAuth2" vs brief "JWT/session" | Local email+password → JWT (HS256). OIDC is a Phase-4 roadmap item. |
| 8 | Running scenarios: researcher "save", analyst "run" | Researcher+ may run and save own scenarios; **analyst+** may export reports and read restricted datasets. |
| 9 | Real district boundaries not available offline | Map uses **schematic hex-tile districts** at approximate centroids, labelled *schematic — not survey/official boundaries*. |
| 10 | All indicator values need official sources; none reachable | All seeded indicator observations are **synthetic, labelled DEMO / SYNTHETIC DATA**, with a `data_sources` row per indicator (`is_demo=true`). |
| 11 | Simulation coefficients have no cited causal source | Coefficients are a **synthetic demo calibration**, displayed as such, with a documented methodology. |
| 12 | Separate `services/` dirs vs "no unnecessary microservices" | Ingestion/retrieval/rag/gis/simulation are **separate Python packages inside the API** (`app/services/*`) with clean interfaces; `services/` at repo root only holds pointers. One deployable backend. |
| 13 | Document approval gate (PRD 5.2) vs demo convenience | Uploads land in `pending_review`; only `approved` docs are searchable. Seed docs are pre-approved. |

## 3. Architecture

```
Browser (Next.js)  ──/api/v1 rewrite──▶  FastAPI
                                          ├─ core: config, security(JWT,RBAC), audit, rate-limit, headers
                                          ├─ services/ingestion : validate → extract → chunk → embed → index
                                          ├─ services/retrieval : query understanding → BM25 + dense → RRF → filter → rerank
                                          ├─ services/rag       : evidence select → LLM → citation validation
                                          ├─ services/gis       : GeoJSON + indicator aggregation + region profile
                                          ├─ services/simulation: model registry → run → sensitivity → provenance/hash
                                          └─ providers          : LLMProvider, EmbeddingProvider, ObjectStore, JobRunner
PostgreSQL(+PostGIS) prod / SQLite dev+test          Redis+Celery (optional; inline runner default)
```

Deployment: `docker-compose.yml` = postgres(postgis) + redis + api + worker + web. Verified locally only on SQLite/inline mode (see README "Verification status").

## 4. Folder structure

```
apps/api/app/{core,models,schemas,api/v1,services/*,providers}
apps/api/{migrations,tests,scripts}
apps/web/{app,components,lib}
packages/types
data/{seed,documents,datasets,gis}
docs/*  docker-compose.yml  .env.example  README.md
```

## 5. Database schema
PRD tables plus: `data_sources` (provenance), `ingestion_jobs`, `annotations`, `saved_queries` (workspace items store JSON payload instead). UUID PKs, `created_at/updated_at`, soft-delete (`deleted_at`) on documents/workspaces/scenarios, FKs, unique + lookup indexes. Geometry stored as GeoJSON JSON; on PostgreSQL the migration additionally adds a PostGIS `geom` column + GiST index (dialect-guarded, unverified here).

## 6. API architecture
Versioned `/api/v1`. Pydantic request/response schemas. Dependency `require_role(...)` on every protected route. Optional-auth dependency for public-readable routes (results filtered by access level). Consistent error body `{error:{code,message}}`.

## 7. Frontend routes
`/ /research /research/results /research/document/[id] /map /map/region/[id] /simulation /simulation/[id] /workspace /workspace/[id] /admin /admin/documents /admin/models /admin/audit /login`

## 8. AI pipeline
Question → query analysis (intent, entities, geography filters) → expansion → hybrid retrieval → diversity-aware evidence selection (max chunks/doc) → prompt with delimited untrusted evidence → LLM returns JSON claims citing `E#` labels → **validator**: unknown ids dropped; claim must lexically/semantically overlap the cited chunk (threshold) else downgraded/removed → answer or **evidence-gap** response if retrieval confidence below threshold. Injection: evidence is data; injected instruction patterns flagged; output never executed/interpreted.

## 9. GIS pipeline
Seed script builds schematic hex-tile district polygons + state hulls → `regions` → observations (demo) → `/gis/layers/{indicator}` returns GeoJSON with joined values → MapLibre choropleth (no external tiles).

## 10. Simulation engine
`ModelDefinition` JSON in `data/seed/models/` → registry (in code, synced to `models` table) → `run_model(inputs, baseline)` returns baseline/scenario/delta, formulas, provenance, limitations, output hash; sensitivity sweep + one-at-a-time tornado; range errors raise `SimulationRangeError`.

## 11. Authentication
bcrypt password hashes, JWT bearer, role claims re-checked against DB, seeded demo accounts per role, in-memory rate limiter on auth/search/ask, security headers, upload validation (extension, magic bytes, size).

## 12. Development phases
1 Foundation → 2 DB + migrations + seed → 3 Evidence vertical slice (search→RAG→citation) → 4 GIS → 5 Simulation → 6 Workspace/RBAC/admin/audit → 7 Frontend integration → 8 Docs/tests.

## 13. Testing strategy
pytest: auth, RBAC matrix, ingestion, search (incl. filters & fusion), RAG citation validation + injection, simulation formulas/boundaries/hash, migration on SQLite, integration flows (question→citation, scenario→save). Frontend: vitest component tests for citation UI + `next build` type-check.

## 14. Delivery status (updated at end of build)
All phases 1–8 implemented for the P0/P1 scope; see README "Verification status" for exactly what was executed vs only authored.
Deviations from this plan: `services/` holds only pointers (code lives in `apps/api/app/services`); `packages/ui` and `packages/config` were not created (components live in `apps/web/components`); `docs/` also gained `MODEL_METHODOLOGY.md`.
