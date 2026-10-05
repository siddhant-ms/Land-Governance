"""Citation validation. The LLM is never trusted: every claim is checked against the retrieved chunks.

A claim survives only if
  1. it cites at least one evidence label that was actually retrieved (unknown ids are discarded),
  2. its content words are sufficiently present in the cited passage (support >= threshold), and
  3. every number in the claim appears in the cited passage (guards against numeric hallucination).
Claims with partial support are kept but flagged; unsupported claims are removed.
"""
import re
from dataclasses import dataclass, field

from app.services.rag.types import EvidenceItem, RawClaim
from app.services.retrieval.text import content_tokens, split_sentences

NUM = re.compile(r"\d+(?:[.,]\d+)?")


@dataclass
class ValidatedClaim:
    text: str
    labels: list[str]  # validated evidence labels
    support: float
    strength: str  # strong | partial
    kind: str
    supporting_span: tuple[int, int] | None  # char offsets in the *best* cited chunk
    best_label: str


@dataclass
class ValidationReport:
    proposed: int = 0
    kept: int = 0
    removed: list[dict] = field(default_factory=list)
    invalid_citation_ids: list[str] = field(default_factory=list)
    downgraded: int = 0


def _support(claim_tokens: set[str], passage: str) -> float:
    if not claim_tokens:
        return 0.0
    return len(claim_tokens & content_tokens(passage)) / len(claim_tokens)


def _numbers_ok(claim: str, passage: str) -> bool:
    nums = {n.replace(",", "") for n in NUM.findall(claim)}
    if not nums:
        return True
    have = {n.replace(",", "") for n in NUM.findall(passage)}
    return nums <= have


def best_span(claim: str, passage: str) -> tuple[int, int] | None:
    """Locate the passage sentence that best supports the claim (used for highlighting)."""
    ct = content_tokens(claim)
    best, best_s = None, 0.0
    for sent in split_sentences(passage) or [passage]:
        s = len(ct & content_tokens(sent)) / max(len(ct), 1)
        if s > best_s:
            best, best_s = sent, s
    if best is None or best_s == 0:
        return None
    i = passage.find(best)
    return (i, i + len(best)) if i >= 0 else None


def validate_claims(raw: list[RawClaim], evidence: dict[str, EvidenceItem], min_support: float) -> tuple[list[ValidatedClaim], ValidationReport]:
    rep = ValidationReport(proposed=len(raw))
    out: list[ValidatedClaim] = []
    for c in raw:
        valid = [lbl for lbl in dict.fromkeys(c.evidence) if lbl in evidence]
        rep.invalid_citation_ids += [lbl for lbl in c.evidence if lbl not in evidence]
        if not valid:
            rep.removed.append({"text": c.text[:160], "reason": "no valid citation"})
            continue
        ct = content_tokens(c.text)
        scored = sorted(((_support(ct, evidence[lbl].text), lbl) for lbl in valid), reverse=True)
        keep = [(s, lbl) for s, lbl in scored if s >= min_support and _numbers_ok(c.text, evidence[lbl].text)]
        if not keep:
            reason = "numeric value not found in cited passage" if any(
                s >= min_support for s, _ in scored) else "cited passage does not support claim"
            rep.removed.append({"text": c.text[:160], "reason": reason})
            continue
        top_support, top_label = keep[0]
        strength = "strong" if top_support >= 0.7 else "partial"
        if strength == "partial":
            rep.downgraded += 1
        out.append(ValidatedClaim(c.text.strip(), [lbl for _, lbl in keep], round(top_support, 3), strength, c.kind,
                                  best_span(c.text, evidence[top_label].text), top_label))
    rep.kept = len(out)
    return out, rep
