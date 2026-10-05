# API reference

Base path `/api/v1`. Interactive docs at `/docs` when `ENVIRONMENT != production`. JSON errors use
`{"error":{"code","message","details"}}`. Auth: `Authorization: Bearer <JWT>` from `POST /auth/login`.

## Roles and capabilities (enforced server-side in `app/core/security.py`)

| Capability | Roles |
|---|---|
| `corpus.read_public` | public, researcher, analyst, expert, admin |
| `map.read_public` | public, researcher, analyst, expert, admin |
| `workspace.write` | researcher, analyst, expert, admin |
| `scenario.run` | researcher, analyst, expert, admin |
| `brief.export` | researcher, analyst, expert, admin |
| `data.restricted` | analyst, expert, admin |
| `scenario.export` | analyst, expert, admin |
| `evidence.review` | expert, admin |
| `model.review` | expert, admin |
| `admin.manage` | admin |

Unauthenticated callers are `public`. Restricted documents/indicators require `data.restricted`; unapproved documents are visible only to `evidence.review` roles.

## Endpoints

| Tag | Method | Path |
|---|---|---|
| admin | GET | `/api/v1/admin/audit` |
| admin | GET | `/api/v1/admin/documents` |
| admin | POST | `/api/v1/admin/documents/ingest` |
| admin | POST | `/api/v1/admin/documents/ingest-url` |
| admin | PATCH | `/api/v1/admin/documents/{doc_id}` |
| admin | POST | `/api/v1/admin/documents/{doc_id}/approve` |
| admin | POST | `/api/v1/admin/documents/{doc_id}/reject` |
| admin | GET | `/api/v1/admin/ingestion/{job_id}` |
| admin | GET | `/api/v1/admin/models` |
| admin | PATCH | `/api/v1/admin/models/{mid}` |
| admin | POST | `/api/v1/admin/models/{mid}/review` |
| admin | GET | `/api/v1/admin/users` |
| admin | PATCH | `/api/v1/admin/users/{uid}/role` |
| auth | POST | `/api/v1/auth/login` |
| auth | GET | `/api/v1/auth/me` |
| auth | POST | `/api/v1/auth/register` |
| dashboard | GET | `/api/v1/dashboard` |
| documents | GET | `/api/v1/documents/{doc_id}` |
| documents | POST | `/api/v1/documents/{doc_id}/annotations` |
| documents | GET | `/api/v1/documents/{doc_id}/annotations` |
| documents | GET | `/api/v1/documents/{doc_id}/chunks/{chunk_id}` |
| documents | GET | `/api/v1/documents/{doc_id}/related` |
| gis | GET | `/api/v1/gis/boundaries` |
| gis | GET | `/api/v1/gis/layers/{ident}` |
| meta | GET | `/api/v1/health` |
| gis | GET | `/api/v1/indicators` |
| gis | GET | `/api/v1/indicators/{ident}/observations` |
| simulation | GET | `/api/v1/models` |
| simulation | GET | `/api/v1/models/{model_id}/baseline` |
| gis | GET | `/api/v1/regions` |
| gis | GET | `/api/v1/regions/{region_id}` |
| search | POST | `/api/v1/research/ask` |
| simulation | GET | `/api/v1/scenarios` |
| simulation | POST | `/api/v1/scenarios` |
| simulation | GET | `/api/v1/scenarios/compare` |
| simulation | GET | `/api/v1/scenarios/{sid}` |
| simulation | POST | `/api/v1/scenarios/{sid}/run` |
| simulation | GET | `/api/v1/scenarios/{sid}/runs/{rid}` |
| simulation | GET | `/api/v1/scenarios/{sid}/runs/{rid}/export` |
| search | POST | `/api/v1/search` |
| search | GET | `/api/v1/search/facets` |
| workspaces | GET | `/api/v1/workspaces` |
| workspaces | POST | `/api/v1/workspaces` |
| workspaces | GET | `/api/v1/workspaces/{wid}` |
| workspaces | GET | `/api/v1/workspaces/{wid}/brief` |
| workspaces | POST | `/api/v1/workspaces/{wid}/items` |
| workspaces | DELETE | `/api/v1/workspaces/{wid}/items/{iid}` |

## Key response contracts

### `POST /research/ask`
```json
{
  "answer": "claim text [1][2] ...",
  "claims": [{"text":"...","citations":["citation_1"],"numbers":[1],"kind":"source_extract|synthesis","support":1.0,"strength":"strong|partial"}],
  "sources": [{"citation_id":"citation_1","number":1,"chunk_id":"…","document_id":"…","title":"…","organization":"…","publication_date":"2024-03-15","page":3,"section":"…","passage":"exact chunk text","highlights":[[start,end]],"source_url":"…","relevance":0.56,"is_demo":true,"explain":{}}],
  "limitations": ["…"], "evidence_gap": false, "evidence_strength": "strong|moderate|weak|none",
  "ai_status": "ok|failed|gap", "retrieved": [...], "pipeline": {"provider":"…","validation":{"proposed":5,"kept":5,"removed":[],"invalid_citation_ids":[]}}
}
```
`evidence_gap=true` returns the message *The available corpus does not contain enough evidence to answer this confidently.* and no claims. `ai_status=failed` keeps `retrieved` so evidence stays visible.

### `POST /scenarios/{id}/run`
Returns `{run_id, result}` where `result` contains `inputs`, `outputs[{baseline,scenario,delta,delta_pct,direction}]`, `equations`, `substituted`, `coefficients`, `coefficient_provenance`, `assumptions`, `limitations`, `sensitivity`, `tornado`, `baseline_context`, `hashes`, `disclaimer`. Out-of-range inputs return `422 SIMULATION_OUT_OF_RANGE` with `details.problems`.

### Error codes of note
`AUTH_REQUIRED` 401 · `INVALID_TOKEN` 401 · `FORBIDDEN` 403 · `RESTRICTED_DOCUMENT` 403 · `RESTRICTED_DATASET` 403 · `DUPLICATE_DOCUMENT` 409 · `UNSUPPORTED_FILE_TYPE` 415 · `FILE_TOO_LARGE` 413 · `SIMULATION_OUT_OF_RANGE` 422 · `RATE_LIMITED` 429