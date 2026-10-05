# SIH26019 — Land Governance Evidence Platform

Evidence-grounded research and policy-scenario platform:
**Question → hybrid evidence retrieval → citation-checked answer → GIS context → transparent scenario simulation → comparison → saved research brief.**

> ⚠ All seeded documents, indicators, boundaries and model coefficients are **DEMO / SYNTHETIC**. See `docs/DATA_SOURCES.md`.

## Verification status (read this first)

| Area | Status |
|---|---|
| Backend (86 pytest tests: auth, RBAC matrix, ingestion, search, RAG + adversarial LLM, prompt injection, simulation, GIS, workspace, audit, migrations, 2 integration flows) | ✅ run, passing — on **SQLite** |
| Frontend (15 vitest tests, `tsc --noEmit`, `next build` for all 16 routes) | ✅ run, passing |
| Full 12-step demo story in real Chromium (Playwright) against live API + web | ✅ run, passing |
| Alembic migration | ✅ upgrade/downgrade verified on SQLite. **PostgreSQL/PostGIS extras (geom column, GiST, GIN FTS) are written but unexecuted** |
| `docker-compose.yml`, Dockerfiles, Celery worker, Redis | ⚠ authored; worker module import-checked only. **Never run** (no Docker in the build sandbox) |
| OpenAI / Anthropic LLM + embedding providers | ⚠ implemented over HTTPS, **never called** (no keys). Validation layer is tested with fake providers |
| OpenSearch / pgvector backends | ❌ not implemented (abstraction only) |
| Grants portal, review-workflow collaboration (PRD P2) | ❌ intentionally not built |

## Quick start (no Docker, no API keys)

```bash
# 1. backend (Python 3.12)
cd apps/api
pip install -r requirements-dev.txt
python -m scripts.seed                    # creates data/dev.sqlite3, ingests 14 demo docs, geography, indicators, models
uvicorn app.main:app --port 8000

# 2. frontend (Node 20+)         — new terminal
cd apps/web
npm install
API_INTERNAL_URL=http://localhost:8000 npm run dev      # http://localhost:3000
```
Demo accounts (password `Demo@12345`): `researcher@demo.sih`, `analyst@demo.sih`, `expert@demo.sih`, `admin@demo.sih`.

## The demo story
1. Home → ask *"What evidence exists on land-record digitization and land-dispute outcomes in India?"*
2. Read the cited answer; click **[1]** → exact passage highlighted, with org/date/page/section/URL/relevance.
3. **Open in document** → lands on the cited chunk. 4. **Map** → pick a state/tile → region profile.
5. **Run scenario** (sign in) → move *Target digitization coverage* 62 → 80 → **Run**.
6. Inspect baseline vs scenario, inputs, formulas, coefficient provenance, sensitivity & tornado, limitations.
7. **Save to workspace** → Workspace → **Export evidence brief**. As analyst: **Export report**. As admin: Admin → Audit.

Try an unanswerable question ("corporate tax rate on offshore wind") to see the evidence-gap response.

## Configuration
Copy `.env.example` → `.env`. Defaults run fully offline (`LLM_PROVIDER=extractive`, `EMBEDDING_PROVIDER=hashing`). To use real models set `LLM_PROVIDER=anthropic|openai`, the matching `*_API_KEY`, and (for embeddings) `EMBEDDING_PROVIDER=openai` then **re-ingest**. `JWT_SECRET` is mandatory when `ENVIRONMENT=production`.

## Common tasks
| Task | Command (from `apps/api` unless noted) |
|---|---|
| Run backend tests | `python -m pytest -q` |
| Run frontend tests / types / build | `cd apps/web && npm test && npm run typecheck && npm run build` |
| Ingest your own documents | put files in `data/documents/` → `python -m scripts.ingest --no-approve` → approve in **Admin → Documents** |
| Migrate a Postgres DB | `DATABASE_URL=postgresql+psycopg://… alembic upgrade head && python -m scripts.seed` |
| Full stack in containers (untested) | `cp .env.example .env` (set `JWT_SECRET`) → `docker compose up --build` |
| Celery worker (untested) | `JOB_BACKEND=celery REDIS_URL=redis://… celery -A app.worker worker -l info` |

## Repository map
`apps/api` FastAPI (+ `app/services/{ingestion,retrieval,rag,gis,simulation}`, `providers`, `seed`, `migrations`, `tests`) · `apps/web` Next.js · `packages/types` shared TS contracts · `data/seed` demo corpus & model JSON · `docs/` plan, architecture, API, data sources, model methodology.

## Security summary
JWT + bcrypt; RBAC enforced server-side per route (role re-read from DB); restricted documents/indicators filtered at retrieval; upload allow-list + magic bytes + size cap + dedupe by SHA-256; SSRF-guarded URL ingest; in-memory rate limits; security headers; parameterised ORM queries; append-only audit log storing hashes of queries; RAG treats retrieved text as data. **Prototype caveats:** token in `localStorage`, in-process rate limiter, demo passwords.
