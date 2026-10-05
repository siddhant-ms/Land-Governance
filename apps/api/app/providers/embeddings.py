"""EmbeddingProvider abstraction: deterministic local hashing (default) or OpenAI."""
import hashlib
import math
from functools import lru_cache
from typing import Protocol

import httpx

from app.core.config import get_settings
from app.services.retrieval.lexicon import concept_of
from app.services.retrieval.text import tokenize

DIM = 384


class EmbeddingProvider(Protocol):
    name: str
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class HashingEmbeddingProvider:
    """Feature-hashed unigram+bigram+concept vectors, L2-normalised.

    NOT a learned semantic model. Deterministic, offline, explainable. Concept features
    (see lexicon.py) give it limited synonym awareness for the land-governance domain.
    """
    name = "hashing-v1"
    dim = DIM

    def _bucket(self, feat: str) -> tuple[int, float]:
        h = hashlib.blake2b(feat.encode(), digest_size=8).digest()
        n = int.from_bytes(h, "big")
        return n % self.dim, 1.0 if (n >> 63) & 1 else -1.0

    def _one(self, text: str) -> list[float]:
        toks = tokenize(text)
        feats: dict[str, float] = {}
        for t in toks:
            feats[f"u:{t}"] = feats.get(f"u:{t}", 0.0) + 1.0
            c = concept_of(t)
            if c:
                feats[f"c:{c}"] = feats.get(f"c:{c}", 0.0) + 1.5
        for a, b in zip(toks, toks[1:]):
            feats[f"b:{a}_{b}"] = feats.get(f"b:{a}_{b}", 0.0) + 1.0
        vec = [0.0] * self.dim
        for f, w in feats.items():
            i, sign = self._bucket(f)
            vec[i] += sign * (1.0 + math.log(w))
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._one(t) for t in texts]


class OpenAIEmbeddingProvider:
    dim = 1536

    def __init__(self, api_key: str, model: str):
        self.api_key, self.model, self.name = api_key, model, f"openai:{model}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        r = httpx.post("https://api.openai.com/v1/embeddings", timeout=60,
                       headers={"Authorization": f"Bearer {self.api_key}"},
                       json={"model": self.model, "input": texts})
        r.raise_for_status()
        return [d["embedding"] for d in r.json()["data"]]


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    s = get_settings()
    if s.embedding_provider == "openai":
        if not s.openai_api_key:
            raise RuntimeError("EMBEDDING_PROVIDER=openai requires OPENAI_API_KEY")
        return OpenAIEmbeddingProvider(s.openai_api_key, s.openai_embedding_model)
    return HashingEmbeddingProvider()
