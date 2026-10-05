# services/

Ingestion, retrieval, RAG, GIS and simulation are **separate Python packages with explicit interfaces**, but they live
inside the single deployable API (`apps/api/app/services/*`) on purpose: one process, one database, no network hops.
Splitting any of them into its own service later only requires moving the package and swapping the function calls for HTTP/queue calls.

| Package | Path | Interface |
|---|---|---|
| ingestion | `apps/api/app/services/ingestion` | `register_upload`, `process_job`, `enqueue` |
| retrieval | `apps/api/app/services/retrieval` | `search_evidence`, `analyze_query` |
| rag | `apps/api/app/services/rag` | `answer_question`, `validate_claims` |
| gis | `apps/api/app/services/gis` | `layer_geojson`, `region_profile` |
| simulation | `apps/api/app/services/simulation` | `run_model`, `execute_run` |
