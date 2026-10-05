"""Hybrid retrieval: BM25 + dense -> Reciprocal Rank Fusion -> (metadata filters applied to the pool) -> rerank.

Design notes
* Filters are applied to the candidate pool *before* fusion so ranks reflect the filtered pool.
* BM25 IDF/avgdl are computed over the whole accessible corpus (not the filtered pool), so scores are stable.
* `relevance` is an ABSOLUTE 0-1 signal (query coverage + cosine) used for evidence-gap decisions; RRF only orders.
* Access control: chunks the caller may not read are removed before anything else.
"""
import math
import re
import time
from collections import OrderedDict

import numpy as np
from sqlalchemy.orm import Session

from app.providers.embeddings import get_embedding_provider
from app.services.retrieval.lexicon import concept_of
from app.services.retrieval.index import ChunkRecord, IndexSnapshot, generation, get_snapshot
from app.services.retrieval.query import analyze_query
from app.services.retrieval.text import _WORD, stem, tokenize
from app.core.security import allowed_access_levels
from app.services.retrieval.types import ChunkHit, QueryAnalysis, SearchFilters, SearchOutcome

K1, B, RRF_K = 1.5, 0.75, 60
AUTHORITY_WEIGHT = {"official": 1.0, "peer_reviewed": 0.9, "institutional": 0.7, "demo": 0.5}
INJECTION_PATTERNS = [re.compile(p, re.I) for p in (
    r"ignore (all |any )?(the )?(previous|prior|above) (instructions|prompts?)",
    r"disregard (all |any )?(the )?(previous|prior|above|system)",
    r"(reveal|print|show|output) (your |the )?(system|hidden) (prompt|instructions)",
    r"you are now (an?|the) ",
    r"new instructions?:",
    r"</?(evidence|system|assistant|instructions?)\b",
)]

_cache: "OrderedDict[tuple, SearchOutcome]" = OrderedDict()
_CACHE_MAX = 256


def looks_like_injection(text: str) -> bool:
    return any(p.search(text) for p in INJECTION_PATTERNS)


def _passes(rec: ChunkRecord, f: SearchFilters, allowed: list[str]) -> bool:
    d = rec.doc
    if d["access_level"] not in allowed:
        return False
    if f.states and d["state_code"] not in f.states:
        return False
    if f.districts and d["district_code"] not in f.districts:
        return False
    pd = d["publication_date"]
    if f.date_from and (pd is None or pd < f.date_from):
        return False
    if f.date_to and (pd is None or pd > f.date_to):
        return False
    if f.source_types and d["authority_level"] not in f.source_types:
        return False
    if f.organizations and d["organization"] not in f.organizations:
        return False
    if f.document_types and d["document_type"] not in f.document_types:
        return False
    if f.topics and not set(f.topics) & set(d["topics"]):
        return False
    return True


def _bm25(snap: IndexSnapshot, weighted_terms: dict[str, float], idxs: list[int]) -> dict[int, float]:
    n = len(snap.records)
    scores: dict[int, float] = {}
    for term, w in weighted_terms.items():
        df = snap.df.get(term, 0)
        if not df:
            continue
        idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
        for i in idxs:
            r = snap.records[i]
            tf = r.tf.get(term, 0)
            if tf:
                denom = tf + K1 * (1 - B + B * r.length / snap.avgdl)
                scores[i] = scores.get(i, 0.0) + w * idf * (tf * (K1 + 1)) / denom
    return scores


def _surface_terms(query_stems: set[str], text: str, limit: int = 8) -> list[str]:
    out: list[str] = []
    for w in _WORD.findall(text.lower()):
        if stem(w) in query_stems and w not in out:
            out.append(w)
            if len(out) >= limit:
                break
    return out


def _boosts(hit: ChunkHit, analysis: QueryAnalysis) -> dict[str, float]:
    d = hit.doc
    b = {"authority": 0.06 * AUTHORITY_WEIGHT.get(d["authority_level"], 0.5)}
    pd = d["publication_date"]
    b["recency"] = 0.03 * max(0.0, min(1.0, (pd.year - 2000) / 26)) if pd else 0.0
    if analysis.states:
        b["geography"] = 0.08 if d["state_code"] in analysis.states else (0.02 if not d["state_code"] else 0.0)
    if analysis.document_types and d["document_type"] in analysis.document_types:
        b["document_type"] = 0.04
    return b


def _search_uncached(db: Session, query: str, f: SearchFilters, role: str, top_k: int) -> SearchOutcome:
    t0 = time.perf_counter()
    analysis = analyze_query(query)
    snap = get_snapshot(db)
    notes: list[str] = []
    allowed = allowed_access_levels(role)
    pool = [i for i, r in enumerate(snap.records) if _passes(r, f, allowed)]
    t1 = time.perf_counter()
    if not pool or not analysis.tokens:
        return SearchOutcome([], analysis, len(pool), {"total": round((time.perf_counter() - t0) * 1000, 1)}, notes=notes)

    # lexical (BM25); expansion terms count half
    weighted = {t: 1.0 for t in analysis.tokens}
    for t in analysis.expansions:
        weighted.setdefault(t, 0.5)
    bm = _bm25(snap, weighted, pool)
    lex_rank = {i: r + 1 for r, (i, _) in enumerate(sorted(bm.items(), key=lambda x: -x[1]))}
    t2 = time.perf_counter()

    # dense
    cos: dict[int, float] = {}
    provider = get_embedding_provider()
    if snap.matrix is not None and snap.dim == provider.dim:
        qv = np.array(provider.embed([query])[0], dtype=np.float32)
        sims = snap.matrix[pool] @ qv
        cos = {i: float(s) for i, s in zip(pool, sims)}
    else:
        notes.append("Dense retrieval disabled: indexed embeddings do not match the configured embedding provider.")
    dense_order = sorted(((i, s) for i, s in cos.items() if s > 0), key=lambda x: -x[1])
    dense_rank = {i: r + 1 for r, (i, _) in enumerate(dense_order)}
    t3 = time.perf_counter()

    # Reciprocal Rank Fusion
    cand = set(lex_rank) | set(dense_rank)
    q_terms = set(analysis.tokens)
    hits: list[ChunkHit] = []
    max_rrf = 2.0 / (RRF_K + 1)
    for i in cand:
        r = snap.records[i]
        rrf = (1 / (RRF_K + lex_rank[i]) if i in lex_rank else 0.0) + (1 / (RRF_K + dense_rank[i]) if i in dense_rank else 0.0)
        # coverage: exact stem match = 1.0, same-concept synonym match = 0.7 (lexicon is shown to users)
        cov = sum(1.0 if t in r.tf else 0.7 if (c := concept_of(t)) and c in r.concepts else 0.0
                  for t in q_terms) / len(q_terms)
        rel = 0.5 * cov + 0.5 * max(0.0, min(1.0, cos.get(i, 0.0)))
        if cov == 0 and cos.get(i, 0.0) < 0.2:  # pure noise: no term, concept or strong semantic overlap
            continue
        h = ChunkHit(r.chunk_id, r.document_id, r.version_id, r.page_no, r.section, r.text, r.doc,
                     bm25=bm.get(i, 0.0), dense=cos.get(i, 0.0), rank_lexical=lex_rank.get(i),
                     rank_dense=dense_rank.get(i), rrf=rrf, coverage=cov, relevance=rel)
        h.boosts = _boosts(h, analysis)
        # rerank: fused rank signal + absolute relevance + authority/recency/geography/doc-type boosts
        h.final_score = 0.55 * (rrf / max_rrf) + 0.30 * rel + sum(h.boosts.values())
        h.matched_terms = _surface_terms(q_terms, r.text)
        h.injection_suspected = looks_like_injection(r.text)
        hits.append(h)
    hits.sort(key=lambda h: -h.final_score)
    t4 = time.perf_counter()
    ms = lambda a, b: round((b - a) * 1000, 1)  # noqa: E731
    return SearchOutcome(hits[:top_k], analysis, len(pool),
                         {"filter": ms(t0, t1), "bm25": ms(t1, t2), "dense": ms(t2, t3), "fuse_rerank": ms(t3, t4),
                          "total": ms(t0, t4)}, notes=notes)


def search_evidence(db: Session, query: str, filters: SearchFilters | None = None, role: str = "public",
                    top_k: int = 10) -> SearchOutcome:
    f = filters or SearchFilters()
    snap = get_snapshot(db)  # also gives us the corpus fingerprint for cache correctness
    key = (query.strip().lower(), f.key(), tuple(allowed_access_levels(role)), top_k, snap.fingerprint, generation())
    if key in _cache:
        _cache.move_to_end(key)
        out = _cache[key]
        return SearchOutcome(out.hits, out.analysis, out.candidates_considered, out.timings_ms, cached=True, notes=out.notes)
    out = _search_uncached(db, query, f, role, top_k)
    _cache[key] = out
    if len(_cache) > _CACHE_MAX:
        _cache.popitem(last=False)
    return out


def clear_search_cache() -> None:
    _cache.clear()


def group_by_document(hits: list[ChunkHit], max_passages: int = 3) -> list[dict]:
    groups: "OrderedDict[str, list[ChunkHit]]" = OrderedDict()
    for h in hits:
        groups.setdefault(h.document_id, []).append(h)
    return [{"document_id": did, "best": hs[0], "passages": hs[:max_passages]} for did, hs in groups.items()]


def snippet_for(text: str, terms: list[str], width: int = 300) -> str:
    if len(text) <= width:
        return text
    pos = min((text.lower().find(t) for t in terms if text.lower().find(t) >= 0), default=0)
    start = max(0, pos - width // 3)
    end = min(len(text), start + width)
    return ("…" if start else "") + text[start:end].strip() + ("…" if end < len(text) else "")


# re-exported for tests
__all__ = ["search_evidence", "group_by_document", "snippet_for", "looks_like_injection", "tokenize"]
