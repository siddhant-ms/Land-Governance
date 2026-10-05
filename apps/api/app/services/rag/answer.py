"""Question -> query analysis -> hybrid retrieval -> evidence selection -> LLM -> citation validation -> answer."""
import logging
from dataclasses import asdict

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.providers.llm import LLMProvider, get_llm_provider
from app.services.rag.types import EvidenceItem
from app.services.rag.validate import validate_claims
from app.services.retrieval.search import group_by_document, search_evidence
from app.services.retrieval.serialize import doc_summary, hit_to_dict
from app.services.retrieval.types import ChunkHit, SearchFilters

log = logging.getLogger(__name__)

GAP_MESSAGE = "The available corpus does not contain enough evidence to answer this confidently."
CAUSAL_WORDS = ("outcome", "impact", "effect", "reduce", "cause", "result in", "lead to", "improve")


def select_evidence(hits: list[ChunkHit], max_per_doc: int, max_total: int, question: str = "") -> tuple[list[EvidenceItem], int]:
    """Diversity-aware selection; drops passages that look like prompt injection."""
    chosen: list[EvidenceItem] = []
    per_doc: dict[str, int] = {}
    excluded = 0
    wants_data = any(w in question.lower() for w in ("dataset", "indicator", "data source", "statistic"))
    top_rel = max((h.relevance for h in hits if not h.injection_suspected), default=0.0)
    for rank, h in enumerate(hits, start=1):
        if h.injection_suspected:
            excluded += 1
            continue
        if h.doc["document_type"] == "dataset_description" and not wants_data:
            continue  # data documentation is not evidence about policy outcomes
        if h.relevance < 0.6 * top_rel:  # skip passages much weaker than the best one
            continue
        if per_doc.get(h.document_id, 0) >= max_per_doc:
            continue
        per_doc[h.document_id] = per_doc.get(h.document_id, 0) + 1
        pd = h.doc["publication_date"]
        chosen.append(EvidenceItem(f"E{len(chosen) + 1}", h.chunk_id, h.document_id, h.text, h.doc["title"],
                                   h.doc["organization"], pd.year if pd else None, h.page_no, h.section, rank))
        if len(chosen) >= max_total:
            break
    return chosen, excluded


def _retrieved_payload(hits: list[ChunkHit]) -> list[dict]:
    out = []
    for g in group_by_document(hits):
        best: ChunkHit = g["best"]
        out.append({**doc_summary(g["document_id"], best.doc), "score": round(best.final_score, 4),
                    "passages": [hit_to_dict(p) for p in g["passages"]]})
    return out


def _gap(question: str, analysis: dict, hits: list[ChunkHit], timings: dict, note: str = "", status: str = "gap") -> dict:
    return {"question": question, "answer": GAP_MESSAGE, "summary": "", "claims": [], "sources": [],
            "limitations": [note] if note else [], "evidence_gap": True, "evidence_gap_message": GAP_MESSAGE,
            "evidence_strength": "none", "ai_status": status, "ai_message": None,
            "retrieved": _retrieved_payload(hits), "query_analysis": analysis, "suggested_followups": [
                "Try broadening the question or removing a geographic filter.",
                "Search the evidence repository directly to browse the closest documents."],
            "pipeline": {"timings_ms": timings}}


def answer_question(db: Session, question: str, filters: SearchFilters | None, role: str,
                    llm: LLMProvider | None = None) -> dict:
    s = get_settings()
    outcome = search_evidence(db, question, filters, role, top_k=20)
    analysis = {**asdict(outcome.analysis), "filters": (filters.active() if filters else {})}
    analysis.pop("original", None)
    hits = outcome.hits
    if not hits:
        return _gap(question, analysis, [], outcome.timings_ms)
    evidence, excluded = select_evidence(hits, s.rag_max_chunks_per_doc, s.rag_max_evidence, question)
    top = max((h for h in hits if not h.injection_suspected), key=lambda h: h.relevance, default=None)
    if not evidence or top is None or top.relevance < s.rag_min_retrieval_score or top.coverage < 0.25:
        return _gap(question, analysis, hits, outcome.timings_ms)

    llm = llm or get_llm_provider()
    try:
        raw = llm.synthesize(question, evidence)
    except Exception as e:  # noqa: BLE001 - provider/network/parse failure must not lose the retrieved evidence
        log.warning("LLM synthesis failed: %s", type(e).__name__)
        gap = _gap(question, analysis, hits, outcome.timings_ms, status="failed")
        gap.update({"answer": "", "evidence_gap": False, "evidence_gap_message": None, "ai_status": "failed",
                    "ai_message": "The research assistant could not complete the synthesis. Your retrieved evidence is still available below.",
                    "suggested_followups": []})
        return gap

    ev_map = {e.label: e for e in evidence}
    claims, report = validate_claims(raw.claims, ev_map, s.rag_min_claim_support)
    if not claims:
        note = ("Generated statements could not be verified against the retrieved passages and were removed."
                if report.proposed else "")
        return _gap(question, analysis, hits, outcome.timings_ms, note)

    # display numbering by order of first citation
    number: dict[str, int] = {}
    for c in claims:
        for lbl in c.labels:
            number.setdefault(lbl, len(number) + 1)
    hit_by_chunk = {h.chunk_id: h for h in hits}
    highlights: dict[str, list[list[int]]] = {}
    for c in claims:
        if c.supporting_span:
            highlights.setdefault(c.best_label, []).append(list(c.supporting_span))

    sources = []
    for lbl, n in sorted(number.items(), key=lambda kv: kv[1]):
        e = ev_map[lbl]
        h = hit_by_chunk[e.chunk_id]
        sources.append({**doc_summary(e.document_id, h.doc), "citation_id": f"citation_{n}", "number": n, "label": lbl,
                        "chunk_id": e.chunk_id, "page": e.page_no, "section": e.section, "passage": e.text,
                        "highlights": highlights.get(lbl, []), "relevance": round(h.relevance, 3), "rank": e.rank,
                        "explain": h.explain()})
    claim_payload = [{"text": c.text, "citations": [f"citation_{number[l]}" for l in c.labels],
                      "numbers": [number[l] for l in c.labels], "kind": c.kind, "support": c.support,
                      "strength": c.strength} for c in claims]
    answer = " ".join(f"{c['text']} " + "".join(f"[{n}]" for n in c["numbers"]) for c in claim_payload)

    n_docs = len({src["document_id"] for src in sources})
    mean_support = sum(c.support for c in claims) / len(claims)
    strength = "strong" if n_docs >= 3 and mean_support >= 0.7 else "moderate" if n_docs >= 2 else "weak"

    lim = ["Answers summarise retrieved passages only; they are not legal advice or a policy recommendation."]
    if any(src["is_demo"] for src in sources):
        lim.append("DEMO CORPUS: cited passages are illustrative text authored for this prototype, not official publications.")
    if raw.provider == "extractive":
        lim.append("Extractive mode: each statement is a verbatim sentence from a source; no generative model was used.")
    if n_docs == 1:
        lim.append("All cited evidence comes from a single document.")
    if report.downgraded:
        lim.append(f"{report.downgraded} statement(s) are only partially supported by their cited passage.")
    if report.removed:
        lim.append(f"{len(report.removed)} model-generated statement(s) were removed because they could not be verified against the retrieved passages.")
    if excluded:
        lim.append(f"{excluded} retrieved passage(s) contained instruction-like text and were excluded from synthesis.")
    if any(w in question.lower() for w in CAUSAL_WORDS):
        lim.append("Retrieved material may describe association rather than proven causation; check each source's method.")
    topics = [t for src in sources for t in src["topics"]]
    followups = [f"What does the evidence say about {t.lower()}?" for t in dict.fromkeys(topics)][:3]

    return {"question": question, "answer": answer, "summary": raw.summary, "claims": claim_payload, "sources": sources,
            "limitations": lim, "evidence_gap": False, "evidence_gap_message": None, "evidence_strength": strength,
            "ai_status": "ok", "ai_message": None, "retrieved": _retrieved_payload(hits), "query_analysis": analysis,
            "suggested_followups": followups,
            "pipeline": {"provider": raw.provider, "model": raw.model, "timings_ms": outcome.timings_ms,
                         "cached_retrieval": outcome.cached, "notes": outcome.notes,
                         "validation": {"proposed": report.proposed, "kept": report.kept, "removed": report.removed,
                                        "invalid_citation_ids": report.invalid_citation_ids,
                                        "downgraded": report.downgraded}}}
