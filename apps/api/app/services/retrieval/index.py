"""In-process index snapshot built from the DB (chunks of approved, current, non-deleted documents).

This is the 'local' SearchBackend data structure: BM25 statistics + dense matrix. Rebuilt whenever the
corpus fingerprint changes (so it stays correct across multiple workers without explicit invalidation).
"""
import threading
from collections import Counter
from dataclasses import dataclass, field
from datetime import date

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Document, DocumentChunk, DocumentVersion
from app.services.retrieval.lexicon import concept_of
from app.services.retrieval.text import tokenize


@dataclass
class ChunkRecord:
    chunk_id: str
    document_id: str
    version_id: str
    page_no: int
    section: str
    text: str
    tf: Counter
    length: int
    doc: dict
    concepts: frozenset = frozenset()


@dataclass
class IndexSnapshot:
    fingerprint: str
    records: list[ChunkRecord] = field(default_factory=list)
    df: Counter = field(default_factory=Counter)
    avgdl: float = 1.0
    matrix: np.ndarray | None = None
    dim: int = 0


_lock = threading.Lock()
_snapshot: IndexSnapshot | None = None
_generation = 0


def invalidate_index() -> None:
    global _snapshot, _generation
    with _lock:
        _snapshot = None
        _generation += 1


def generation() -> int:
    return _generation


def _fingerprint(db: Session) -> str:
    n_chunks = db.scalar(select(func.count(DocumentChunk.id))) or 0
    n_docs, last = db.execute(select(func.count(Document.id), func.max(Document.updated_at))
                              .where(Document.status == "approved", Document.deleted_at.is_(None))).one()
    return f"{n_chunks}:{n_docs}:{last}:{_generation}"


def _doc_dict(d: Document) -> dict:
    return {
        "title": d.title, "organization": d.organization, "publication_date": d.publication_date,
        "document_type": d.document_type, "authority_level": d.authority_level, "state_code": d.state_code,
        "district_code": d.district_code, "geography": d.geography_label, "source_url": d.source_url,
        "access_level": d.access_level, "is_demo": d.is_demo, "topics": [t.name for t in d.topics],
        "authors": d.authors or [],
    }


def get_snapshot(db: Session) -> IndexSnapshot:
    global _snapshot
    fp = _fingerprint(db)
    snap = _snapshot
    if snap and snap.fingerprint == fp:
        return snap
    rows = db.execute(
        select(DocumentChunk, Document)
        .join(Document, Document.id == DocumentChunk.document_id)
        .join(DocumentVersion, DocumentVersion.id == DocumentChunk.document_version_id)
        .where(Document.status == "approved", Document.deleted_at.is_(None), DocumentVersion.is_current.is_(True))
        .order_by(DocumentChunk.document_id, DocumentChunk.chunk_index)
    ).all()
    doc_cache: dict = {}
    records: list[ChunkRecord] = []
    df: Counter = Counter()
    vecs: list[list[float]] = []
    for ch, doc in rows:
        if doc.id not in doc_cache:
            doc_cache[doc.id] = _doc_dict(doc)
        d = doc_cache[doc.id]
        # title + section are indexed with the passage so BM25 can match on them (title counted once)
        toks = tokenize(f"{d['title']} {ch.section} {ch.text}")
        tf = Counter(toks)
        df.update(tf.keys())
        records.append(ChunkRecord(str(ch.id), str(ch.document_id), str(ch.document_version_id), ch.page_no,
                                   ch.section, ch.text, tf, max(len(toks), 1), d,
                                   frozenset(c for t in tf if (c := concept_of(t)))))
        vecs.append(ch.embedding or [])
    dims = {len(v) for v in vecs if v}
    dim = dims.pop() if len(dims) == 1 else 0
    matrix = np.array([v if len(v) == dim else [0.0] * dim for v in vecs], dtype=np.float32) if dim and vecs else None
    snap = IndexSnapshot(fp, records, df, (sum(r.length for r in records) / len(records)) if records else 1.0, matrix, dim)
    with _lock:
        _snapshot = snap
    return snap


def last_snapshot_fingerprint() -> str | None:
    return _snapshot.fingerprint if _snapshot else None


def _unused(_: date) -> None:  # keeps `date` import explicit for type checkers
    return None
