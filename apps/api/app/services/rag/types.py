from dataclasses import dataclass, field


@dataclass
class EvidenceItem:
    label: str  # E1, E2 ... the ONLY identifiers an LLM may cite
    chunk_id: str
    document_id: str
    text: str
    title: str
    organization: str
    year: int | None
    page_no: int
    section: str
    rank: int


@dataclass
class RawClaim:
    text: str
    evidence: list[str]  # labels as emitted by the model (untrusted until validated)
    kind: str = "synthesis"  # synthesis | source_extract


@dataclass
class RawSynthesis:
    claims: list[RawClaim]
    summary: str = ""
    provider: str = ""
    model: str = ""
    limitations: list[str] = field(default_factory=list)
