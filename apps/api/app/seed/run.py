"""Idempotent full demo seed: identity, corpus, geography/indicators, models, demo workspace + scenario."""
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import REPO_ROOT
from app.models import Document, Region, Scenario, SimModel, User, Workspace, WorkspaceItem
from app.seed.corpus import ingest_directory
from app.seed.gis import seed_gis
from app.seed.identity import seed_identity
from app.services.rag.answer import answer_question
from app.services.simulation.service import create_scenario, execute_run, sync_models_from_files, derive_baseline

QUESTION = "What evidence exists on land-record digitization and land-dispute outcomes in India?"


def seed_all(db: Session) -> dict:
    report: dict = {}
    seed_identity(db)
    report["gis"] = seed_gis(db)
    report["models"] = sync_models_from_files(db)
    if not db.scalar(select(Document).limit(1)):
        report["documents"] = ingest_directory(db, REPO_ROOT / "data" / "seed" / "documents")
    else:
        report["documents"] = "skipped (already seeded)"
    _seed_demo_workspace(db)
    return report


def _seed_demo_workspace(db: Session) -> None:
    researcher = db.scalar(select(User).where(User.email == "researcher@demo.sih"))
    if not researcher or db.scalar(select(Workspace).where(Workspace.owner_id == researcher.id)):
        return
    ka = db.scalar(select(Region).where(Region.state_code == "KA", Region.level == "state"))
    model = db.scalar(select(SimModel).where(SimModel.status == "active"))
    if not (ka and model):
        return
    base, _ = derive_baseline(db, model.definition, ka)
    sc = create_scenario(db, researcher, model.id, "Karnataka: 80% digitization (demo)", ka.id,
                         {**base, "target_coverage": 80.0, "implementation_capacity": 0.8, "data_quality": 0.85},
                         "Seeded example scenario (DEMO calibration).")
    run = execute_run(db, sc, researcher)
    ans = answer_question(db, QUESTION, None, "researcher")
    ws = Workspace(owner_id=researcher.id, title="Land-record digitization and disputes",
                   research_question=QUESTION, description="Seeded example workspace (DEMO data).")
    db.add(ws)
    db.flush()
    db.add(WorkspaceItem(workspace_id=ws.id, item_type="answer", title="Cited answer", payload={
        "claims": ans["claims"], "question": QUESTION}))
    for s in ans["sources"][:4]:
        db.add(WorkspaceItem(workspace_id=ws.id, item_type="citation", ref_id=s["chunk_id"], title=s["title"], payload={
            k: s[k] for k in ("title", "organization", "publication_date", "page", "section", "passage", "source_url", "is_demo", "document_id", "chunk_id")}))
    db.add(WorkspaceItem(workspace_id=ws.id, item_type="scenario", ref_id=str(sc.id), title=sc.name, payload={
        "scenario_id": str(sc.id), "run_id": str(run.id), "outputs": run.output_json["outputs"], "model_name": model.name,
        "model_version": model.version, "input_hash": run.input_hash}))
    db.add(WorkspaceItem(workspace_id=ws.id, item_type="note", title="Note", note="Compare coverage gains with capacity and data-quality assumptions before drawing conclusions."))
    db.commit()
