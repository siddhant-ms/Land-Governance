"""Query understanding: intent, entity extraction and lexicon-based expansion (all shown to the user)."""
import re

from app.services.retrieval.lexicon import expand_terms
from app.services.retrieval.text import tokenize
from app.services.retrieval.types import QueryAnalysis

STATES = {
    "andhra pradesh": "AP", "arunachal pradesh": "AR", "assam": "AS", "bihar": "BR", "chhattisgarh": "CG",
    "goa": "GA", "gujarat": "GJ", "haryana": "HR", "himachal pradesh": "HP", "jharkhand": "JH",
    "karnataka": "KA", "kerala": "KL", "madhya pradesh": "MP", "maharashtra": "MH", "manipur": "MN",
    "meghalaya": "ML", "mizoram": "MZ", "nagaland": "NL", "odisha": "OD", "orissa": "OD", "punjab": "PB",
    "rajasthan": "RJ", "sikkim": "SK", "tamil nadu": "TN", "telangana": "TG", "tripura": "TR",
    "uttar pradesh": "UP", "uttarakhand": "UK", "west bengal": "WB",
}
DOC_TYPE_HINTS = {
    "legal_text": ("law", "act", "statute", "legal", "court", "regulation", "registration act"),
    "case_study": ("case study", "case studies", "pilot", "experience"),
    "research_paper": ("paper", "study", "studies", "literature", "research", "evaluation"),
    "policy_report": ("report", "policy", "guideline", "framework"),
}


def analyze_query(q: str) -> QueryAnalysis:
    ql = q.lower()
    tokens = tokenize(q)
    states = sorted({code for name, code in STATES.items() if re.search(rf"\b{re.escape(name)}\b", ql)})
    years = [int(y) for y in re.findall(r"\b(19[89]\d|20[0-4]\d)\b", ql)]
    doc_types = [t for t, hints in DOC_TYPE_HINTS.items() if any(h in ql for h in hints)]
    if any(w in ql for w in ("what if", "scenario", "simulate", "increase coverage", "target coverage")):
        intent = "scenario_question"
    elif any(w in ql for w in ("map", "district", "region", "where", "spatial", "geograph")):
        intent = "spatial_question"
    elif any(w in ql for w in ("legal", "law", "act ", "statute", "court")):
        intent = "legal_evidence_question"
    elif any(w in ql for w in ("literature", "papers", "studies", "research on")):
        intent = "literature_search"
    else:
        intent = "policy_question"
    return QueryAnalysis(q, tokens, expand_terms(tokens), intent, states, years, doc_types)
