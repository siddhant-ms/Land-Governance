"""Tokenisation shared by BM25, hashing embeddings and citation validation."""
import re

STOPWORDS = frozenset("""a an and are as at be been being by can could did do does for from had has have how i in into is it its
of on or our shall should so such than that the their them then there these they this those to was were what when where which while
who whom why will with would you your about across also any both each few more most other over same some than too very""".split())

_WORD = re.compile(r"[a-z0-9]+")

# Order matters: longest suffixes first. Deliberately light (not a full Porter stemmer).
_SUFFIXES = ("izations", "ization", "isation", "isations", "ations", "ation", "ments", "ment", "ities", "ity",
             "ings", "ing", "ized", "ised", "izing", "ising", "ize", "ise", "ies", "ied", "ed", "es", "s")


def stem(tok: str) -> str:
    if len(tok) <= 4 or tok.isdigit():
        return tok
    for suf in _SUFFIXES:
        if tok.endswith(suf) and len(tok) - len(suf) >= 3:
            base = tok[: -len(suf)]
            if suf in ("ies", "ied"):
                base += "y"
            return base
    return tok


def tokenize(text: str, *, keep_stopwords: bool = False) -> list[str]:
    toks = _WORD.findall(text.lower())
    if not keep_stopwords:
        toks = [t for t in toks if t not in STOPWORDS and len(t) > 1]
    return [stem(t) for t in toks]


def content_tokens(text: str) -> set[str]:
    return set(tokenize(text))


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])", text.strip())
    return [p.strip() for p in parts if len(p.strip()) > 20]
