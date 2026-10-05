"""Small, transparent domain lexicon for land governance.

Used for (a) query expansion and (b) concept features in the local hashing embedding.
This is an explainable stand-in for a learned semantic model: swap EMBEDDING_PROVIDER=openai
for true dense semantics. Every expansion is shown to the user in the search response.
"""
from app.services.retrieval.text import stem

CONCEPTS: dict[str, list[str]] = {
    "digitization": ["digitization", "digitisation", "digitized", "computerization", "computerisation", "online",
                     "e-governance", "digital", "electronic", "automated", "automation", "dilrmp", "bhoomi"],
    "dispute": ["dispute", "disputes", "litigation", "conflict", "conflicts", "court", "cases", "grievance",
                "contested", "adjudication", "resolution", "pendency"],
    "record": ["record", "records", "registry", "register", "mutation", "khata", "ror", "title", "cadastral", "survey"],
    "capacity": ["capacity", "staff", "training", "workload", "backlog", "processing", "administrative", "personnel"],
    "climate": ["climate", "flood", "cyclone", "coastal", "drought", "vulnerability", "resilience", "sea-level", "erosion"],
    "gender": ["women", "gender", "inheritance", "joint", "female", "widow"],
    "landuse": ["land-use", "landuse", "agricultural", "cropland", "forest", "conversion", "urbanization"],
    "spatial": ["map", "maps", "boundary", "boundaries", "gis", "geospatial", "parcel", "parcels", "satellite", "drone"],
}

_STEM_TO_CONCEPT: dict[str, str] = {}
_STEM_TO_WORD: dict[str, str] = {}
for concept, words in CONCEPTS.items():
    for w in words:
        _STEM_TO_CONCEPT[stem(w)] = concept
        _STEM_TO_WORD.setdefault(stem(w), w)


def concept_of(token: str) -> str | None:
    return _STEM_TO_CONCEPT.get(token)


def expand_terms(tokens: list[str]) -> list[str]:
    """Return additional (stemmed) terms drawn from concepts present in the query, excluding originals."""
    have = set(tokens)
    extra: list[str] = []
    seen_concepts = {c for t in tokens if (c := concept_of(t))}
    for c in seen_concepts:
        for w in CONCEPTS[c][:6]:
            s = stem(w)
            if s not in have and s not in extra:
                extra.append(s)
    return extra


def display_word(stem_: str) -> str:
    """Human-readable form of an expansion stem (for the UI only; retrieval uses stems)."""
    return _STEM_TO_WORD.get(stem_, stem_)
