"""Ingest files from a folder (default data/documents) with an optional metadata.csv manifest.

    python -m scripts.ingest [--dir ../../data/documents] [--manifest metadata.csv] [--no-approve]

Manifest columns: file,title,authors(|-separated),organization,publication_date,document_type,authority_level,
state_code,geography_label,access_level,topics(|-separated),source_url,is_demo,provenance_note
Documents land as `pending_review` with --no-approve (recommended for real material).
"""
import argparse
from pathlib import Path

import app.models  # noqa: F401
from app.core.config import REPO_ROOT
from app.core.db import SessionLocal
from app.seed.corpus import ingest_directory

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=str(REPO_ROOT / "data" / "documents"))
    ap.add_argument("--manifest", default=None)
    ap.add_argument("--no-approve", action="store_true")
    a = ap.parse_args()
    d = Path(a.dir)
    manifest = Path(a.manifest) if a.manifest else d / "metadata.csv"
    with SessionLocal() as db:
        for line in ingest_directory(db, d, manifest, auto_approve=not a.no_approve):
            print(line)
