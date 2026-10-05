from dataclasses import asdict, dataclass, field
from datetime import date


@dataclass
class SearchFilters:
    states: list[str] = field(default_factory=list)
    districts: list[str] = field(default_factory=list)
    date_from: date | None = None
    date_to: date | None = None
    source_types: list[str] = field(default_factory=list)  # authority_level: official|peer_reviewed|institutional|demo
    organizations: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    document_types: list[str] = field(default_factory=list)

    def key(self) -> str:
        d = asdict(self)
        return repr(sorted((k, repr(v)) for k, v in d.items()))

    def active(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v}


@dataclass
class QueryAnalysis:
    original: str
    tokens: list[str]
    expansions: list[str]
    intent: str
    states: list[str]
    years: list[int]
    document_types: list[str]


@dataclass
class ChunkHit:
    chunk_id: str
    document_id: str
    version_id: str
    page_no: int
    section: str
    text: str
    doc: dict  # title, organization, publication_date, document_type, authority_level, state_code, ...
    bm25: float = 0.0
    dense: float = 0.0
    rank_lexical: int | None = None
    rank_dense: int | None = None
    rrf: float = 0.0
    coverage: float = 0.0
    relevance: float = 0.0  # absolute 0-1 confidence used for evidence-gap decisions
    boosts: dict = field(default_factory=dict)
    final_score: float = 0.0
    matched_terms: list[str] = field(default_factory=list)
    injection_suspected: bool = False

    def explain(self) -> dict:
        return {"bm25": round(self.bm25, 4), "dense_cosine": round(self.dense, 4), "rank_lexical": self.rank_lexical,
                "rank_dense": self.rank_dense, "rrf": round(self.rrf, 5), "query_coverage": round(self.coverage, 3),
                "relevance": round(self.relevance, 3), "boosts": {k: round(v, 3) for k, v in self.boosts.items()},
                "final_score": round(self.final_score, 4), "matched_terms": self.matched_terms}


@dataclass
class SearchOutcome:
    hits: list[ChunkHit]
    analysis: QueryAnalysis
    candidates_considered: int
    timings_ms: dict
    cached: bool = False
    notes: list[str] = field(default_factory=list)
