// Shared API contracts (mirrors apps/api responses). Type-only: erased at compile time.
export type Role = 'public' | 'researcher' | 'analyst' | 'expert' | 'admin';
export interface User { id: string; name: string; email: string; role: Exclude<Role, 'public'>; organization: string | null }

export interface Filters {
  states?: string[]; organizations?: string[]; topics?: string[]; document_types?: string[]; source_types?: string[];
  date_from?: string; date_to?: string;
}

export interface Explain {
  bm25: number; dense_cosine: number; rank_lexical: number | null; rank_dense: number | null; rrf: number;
  query_coverage: number; relevance: number; boosts: Record<string, number>; final_score: number; matched_terms: string[];
}
export interface Passage {
  chunk_id: string; document_id: string; page: number; section: string; snippet: string; matched_terms: string[];
  relevance: number; score: number; explain: Explain; injection_suspected: boolean;
}
export interface DocSummary {
  document_id: string; title: string; organization: string; publication_date: string | null; year: number | null;
  document_type: string; authority_level: string; state_code: string | null; geography: string; source_url: string;
  access_level: string; is_demo: boolean; topics: string[];
}
export interface SearchResult extends DocSummary { score: number; relevance: number; why_matched: { matched_terms: string[]; explain: Explain }; passages: Passage[] }
export interface SearchResponse {
  query: string; results: SearchResult[]; total_documents: number; candidates_considered: number; cached: boolean;
  query_analysis: { tokens: string[]; expansions: string[]; intent: string; states: string[]; years: number[]; document_types: string[] };
  timings_ms: Record<string, number>; notes: string[]; empty_message: string | null;
}

export interface Source extends DocSummary {
  citation_id: string; number: number; label: string; chunk_id: string; page: number; section: string; passage: string;
  highlights: [number, number][]; relevance: number; rank: number; explain: Explain;
}
export interface Claim { text: string; citations: string[]; numbers: number[]; kind: 'source_extract' | 'synthesis'; support: number; strength: 'strong' | 'partial' }
export interface AskResponse {
  question: string; answer: string; summary: string; claims: Claim[]; sources: Source[]; limitations: string[];
  evidence_gap: boolean; evidence_gap_message: string | null; evidence_strength: 'strong' | 'moderate' | 'weak' | 'none';
  ai_status: 'ok' | 'failed' | 'gap'; ai_message: string | null;
  retrieved: (DocSummary & { score: number; passages: Passage[] })[];
  query_analysis: Record<string, unknown>; suggested_followups: string[];
  pipeline: { provider?: string; model?: string; timings_ms: Record<string, number>; validation?: { proposed: number; kept: number; removed: { text: string; reason: string }[]; invalid_citation_ids: string[]; downgraded: number } };
}

export interface ChunkDetail {
  chunk: { id: string; page: number; section: string; text: string; index: number; indexed_metadata: Record<string, unknown> };
  document: DocumentDetail; context: { before: string | null; after: string | null };
}
export interface DocumentDetail {
  id: string; title: string; authors: string[]; organization: string; source_url: string; document_type: string;
  authority_level: string; language: string; publication_date: string | null; state_code: string | null; geography: string;
  access_level: string; status: string; is_demo: boolean; provenance_note: string; topics: string[]; extraction_quality: number | null;
  version: { version_no: number; content_hash: string; pages: number } | null;
  chunks?: { id: string; index: number; page: number; section: string; text: string }[];
}

export interface IndicatorInfo {
  id: string; key: string; name: string; unit: string; category: string; description: string; higher_is_better: boolean;
  legend: [number, number]; access_level: string; locked: boolean; periods: number[]; is_demo: boolean; demo_label: string | null;
  source: { name: string; description: string; is_demo: boolean; license: string } | null;
}
export interface RegionLite { id: string; name: string; level: 'state' | 'district'; state_code: string; district_code: string | null; centroid: [number, number]; schematic: boolean }
export interface LayerCollection {
  type: 'FeatureCollection';
  features: { type: 'Feature'; geometry: unknown; properties: { region_id: string; name: string; state_code: string; value?: number | null } }[];
  meta: { indicator: IndicatorInfo; period: number; periods: number[]; level: string; geometry_note: string };
}
export interface RegionProfile {
  region: { id: string; name: string; level: string; state_code: string; schematic: boolean; parent: { id: string; name: string } | null; n_districts: number; geometry_note: string };
  indicators: (IndicatorInfo & { latest: { period: number; value: number } | null; series: { period: number; value: number }[]; trend: { from: number; to: number; change: number; direction: string; favourable: boolean | null } | null })[];
  documents: DocSummary[]; research: DocSummary[]; aggregation_note: string | null;
  scenario_shortcut: { model_id: string; model_name: string; region_id: string; baseline_coverage: number } | null;
}

export interface ModelParam { key: string; label: string; unit: string; min: number; max: number; default: number; step: number; description: string; baseline_indicator?: string }
export interface SimModel {
  id: string; key: string; name: string; version: string; description: string; methodology: string; review_status: string;
  parameters: ModelParam[]; equations: { output: string; formula: string }[]; coefficients: Record<string, number>;
  coefficient_provenance: Record<string, string>; assumptions: string[]; limitations: string[]; is_demo_calibration: boolean;
}
export interface SimOutput { key: string; label: string; unit: string; higher_is_better: boolean; baseline: number; scenario: number; delta: number; delta_pct: number | null; direction: 'improved' | 'worsened' | 'unchanged' }
export interface SimResult {
  disclaimer: string; is_demo_calibration: boolean; inputs: { key: string; label: string; unit: string; value: number; baseline_value: number; changed: boolean; min: number; max: number }[];
  baseline_context: { region?: { name: string; level: string }; period?: number; sources?: { indicator: string; period: number; source: string; is_demo: boolean }[]; is_demo?: boolean; note?: string };
  outputs: SimOutput[]; equations: { output: string; formula: string }[]; substituted: string[]; coefficients: Record<string, number>;
  coefficient_provenance: Record<string, string>; assumptions: string[]; limitations: string[];
  sensitivity: Record<string, { parameter: string; label: string; unit: string; current: number; points: ({ value: number } & Record<string, number>)[] }>;
  tornado: { parameter: string; label: string; low_output: number | null; high_output: number | null; base_output: number; swing: number; low_value: number; high_value: number }[];
  hashes: { input_hash: string; output_hash: string }; model: { id: string; name: string; version: string; review_status: string }; scenario: { id: string; name: string };
}
export interface ScenarioRow { id: string; name: string; model: { name: string; version: string }; region: { id: string; name: string } | null; parameters: Record<string, number>; latest_run_id: string | null; created_at: string; summary?: { key: string; label: string; baseline: number; scenario: number; delta_pct: number | null }[] }

export interface WorkspaceItem { id: string; item_type: string; ref_id: string | null; title: string; payload: Record<string, any>; note: string; tags: string[]; created_at: string }
export interface Workspace { id: string; title: string; description: string; research_question: string; counts: Record<string, number>; updated_at: string; items?: WorkspaceItem[] }

export interface Dashboard {
  role: Role; corpus_notice: string | null;
  counts: { documents: number; case_studies: number; research_papers: number; datasets: number; passages: number; regions: number; observations: number; demo_documents: number };
  featured_indicators: { key: string; name: string; unit: string; period: number; demo_label: string; by_state: { state: string; state_code: string; value: number }[] }[];
  recent_documents: { id: string; title: string; organization: string; document_type: string; year: number | null; is_demo: boolean }[];
  recent_scenarios: { id: string; name: string; run_id: string | null }[]; recent_workspaces: { id: string; title: string; items: number }[];
}
