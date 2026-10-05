"""Bulk-ingest a folder of documents (optionally described by a metadata CSV manifest)."""
import csv
from pathlib import Path

from sqlalchemy.orm import Session

from app.services.ingestion.pipeline import process_job, register_upload

CSV_LIST_FIELDS = ("authors", "topics")


def _row_to_meta(row: dict) -> dict:
    meta = {k: v for k, v in row.items() if k != "file" and v not in (None, "")}
    for f in CSV_LIST_FIELDS:
        if f in meta:
            meta[f] = [x.strip() for x in meta[f].split("|") if x.strip()]
    if "is_demo" in meta:
        meta["is_demo"] = str(meta["is_demo"]).lower() in ("1", "true", "yes")
    return meta


def ingest_directory(db: Session, directory: Path, manifest: Path | None = None, auto_approve: bool = True) -> list[str]:
    """Metadata precedence: manifest CSV row > file front-matter/PDF info. Returns titles ingested."""
    overrides: dict[str, dict] = {}
    if manifest and manifest.exists():
        with manifest.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                overrides[row["file"]] = _row_to_meta(row)
    done: list[str] = []
    for path in sorted(directory.iterdir()):
        if path.suffix.lower() not in (".md", ".txt", ".pdf") or path.name.startswith("_"):
            continue
        doc, job = register_upload(db, filename=path.name, data=path.read_bytes(),
                                   metadata=overrides.get(path.name, {}), actor=None, auto_approve=auto_approve)
        process_job(job.id)
        db.refresh(doc)
        done.append(f"{doc.status}: {doc.title}")
    return done
