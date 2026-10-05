from app.services.retrieval.search import snippet_for
from app.services.retrieval.types import ChunkHit


def doc_summary(doc_id: str, d: dict) -> dict:
    pd = d["publication_date"]
    return {"document_id": doc_id, "title": d["title"], "organization": d["organization"],
            "publication_date": pd.isoformat() if pd else None, "year": pd.year if pd else None,
            "document_type": d["document_type"], "authority_level": d["authority_level"],
            "state_code": d["state_code"], "geography": d["geography"], "source_url": d["source_url"],
            "access_level": d["access_level"], "is_demo": d["is_demo"], "topics": d["topics"]}


def hit_to_dict(h: ChunkHit, *, full_text: bool = False) -> dict:
    out = {
        "chunk_id": h.chunk_id, "document_id": h.document_id, "page": h.page_no, "section": h.section,
        "snippet": snippet_for(h.text, h.matched_terms), "matched_terms": h.matched_terms,
        "relevance": round(h.relevance, 3), "score": round(h.final_score, 4), "explain": h.explain(),
        "injection_suspected": h.injection_suspected,
    }
    if full_text:
        out["text"] = h.text
    return out
