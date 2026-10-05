from dataclasses import asdict

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import audit
from app.core.db import get_db
from app.core.ratelimit import rate_limit
from app.core.security import optional_user, role_of
from app.models import User
from app.schemas.common import AskIn, SearchIn
from app.services.rag.answer import answer_question
from app.services.retrieval.index import get_snapshot
from app.services.retrieval.lexicon import display_word
from app.services.retrieval.search import group_by_document, search_evidence
from app.services.retrieval.serialize import doc_summary, hit_to_dict

router = APIRouter(tags=["search"])


@router.post("/search", dependencies=[Depends(rate_limit("search", 60, 60))])
def search(body: SearchIn, request: Request, db: Session = Depends(get_db), user: User | None = Depends(optional_user)):
    role = role_of(user)
    f = body.filters.to_filters()
    out = search_evidence(db, body.query, f, role, top_k=body.top_k * 3)
    groups = group_by_document(out.hits)[: body.top_k]
    results = [{**doc_summary(g["document_id"], g["best"].doc), "score": round(g["best"].final_score, 4),
                "relevance": round(g["best"].relevance, 3),
                "why_matched": {"matched_terms": g["best"].matched_terms, "explain": g["best"].explain()},
                "passages": [hit_to_dict(p) for p in g["passages"]]} for g in groups]
    audit.record(db, request, user, "SEARCH_EXECUTED", "search", "",
                 {"query_sha": audit.qhash(body.query), "query_len": len(body.query), "filters": f.active() and list(f.active()),
                  "results": len(results), "cached": out.cached})
    a = asdict(out.analysis)
    a.pop("original")
    a["expansions"] = [display_word(t) for t in a["expansions"]]
    return {"query": body.query, "results": results, "total_documents": len(results),
            "candidates_considered": out.candidates_considered, "query_analysis": a, "timings_ms": out.timings_ms,
            "cached": out.cached, "notes": out.notes,
            "empty_message": None if results else "No sufficiently relevant evidence was found. Try broadening your question or removing a geographic filter."}


@router.post("/research/ask", dependencies=[Depends(rate_limit("ask", 20, 60))])
def ask(body: AskIn, request: Request, db: Session = Depends(get_db), user: User | None = Depends(optional_user)):
    res = answer_question(db, body.question, body.filters.to_filters(), role_of(user))
    audit.record(db, request, user, "AI_QUERY_EXECUTED", "research", "",
                 {"query_sha": audit.qhash(body.question), "evidence_gap": res["evidence_gap"], "ai_status": res["ai_status"],
                  "claims": len(res["claims"]), "provider": res.get("pipeline", {}).get("provider")})
    return res


@router.get("/search/facets")
def facets(db: Session = Depends(get_db), user: User | None = Depends(optional_user)):
    from app.core.security import allowed_access_levels
    allowed = allowed_access_levels(role_of(user))
    docs: dict[str, dict] = {}
    for r in get_snapshot(db).records:
        if r.doc["access_level"] in allowed:
            docs[r.document_id] = r.doc
    def uniq(key): return sorted({d[key] for d in docs.values() if d[key]})
    years = [d["publication_date"].year for d in docs.values() if d["publication_date"]]
    return {"states": uniq("state_code"), "organizations": uniq("organization"), "document_types": uniq("document_type"),
            "source_types": uniq("authority_level"), "topics": sorted({t for d in docs.values() for t in d["topics"]}),
            "year_range": [min(years), max(years)] if years else None, "documents": len(docs)}
