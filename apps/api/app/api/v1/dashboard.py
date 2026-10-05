from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import allowed_access_levels, optional_user, role_of
from app.models import Document, DocumentChunk, Indicator, Observation, Region, Scenario, ScenarioRun, User
from app.services.gis.service import DEMO_BADGE
from app.services.simulation.service import latest_period, region_value

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), user: User | None = Depends(optional_user)):
    role = role_of(user)
    vis = [Document.status == "approved", Document.deleted_at.is_(None), Document.access_level.in_(allowed_access_levels(role))]
    by_type = dict(db.execute(select(Document.document_type, func.count()).where(*vis).group_by(Document.document_type)).all())
    n_docs = sum(by_type.values())
    n_demo = db.scalar(select(func.count()).where(*vis, Document.is_demo.is_(True))) or 0
    recent_docs = db.scalars(select(Document).where(*vis).order_by(Document.publication_date.desc()).limit(5)).all()
    feats = []
    for key in ("digitization_coverage", "dispute_pressure_index", "climate_vulnerability_index"):
        ind = db.scalar(select(Indicator).where(Indicator.key == key))
        if not ind:
            continue
        per = latest_period(db, ind.id)
        states = db.scalars(select(Region).where(Region.level == "state").order_by(Region.name)).all()
        feats.append({"key": key, "name": ind.name, "unit": ind.unit, "period": per, "demo_label": DEMO_BADGE,
                      "by_state": [{"state": s.name, "state_code": s.state_code, "value": round(region_value(db, s, ind, per) or 0, 2)} for s in states]})
    d = {"role": role,
         "counts": {"documents": n_docs, "case_studies": by_type.get("case_study", 0), "research_papers": by_type.get("research_paper", 0),
                    "datasets": db.scalar(select(func.count(Indicator.id))), "passages": db.scalar(select(func.count(DocumentChunk.id))),
                    "regions": db.scalar(select(func.count(Region.id))), "observations": db.scalar(select(func.count(Observation.id))),
                    "demo_documents": n_demo},
         "corpus_notice": "The seeded corpus and all indicator values are DEMO / SYNTHETIC. Nothing here is an official statistic." if n_demo else None,
         "featured_indicators": feats,
         "recent_documents": [{"id": str(d.id), "title": d.title, "organization": d.organization, "document_type": d.document_type,
                               "year": d.publication_date.year if d.publication_date else None, "is_demo": d.is_demo} for d in recent_docs],
         "recent_scenarios": [], "recent_workspaces": []}
    if user:
        from app.models import Workspace
        for s in db.scalars(select(Scenario).where(Scenario.owner_id == user.id, Scenario.deleted_at.is_(None)).order_by(Scenario.created_at.desc()).limit(4)):
            run = db.scalar(select(ScenarioRun).where(ScenarioRun.scenario_id == s.id).order_by(ScenarioRun.created_at.desc()))
            d["recent_scenarios"].append({"id": str(s.id), "name": s.name, "run_id": str(run.id) if run else None})
        for w in db.scalars(select(Workspace).where(Workspace.owner_id == user.id, Workspace.deleted_at.is_(None)).order_by(Workspace.updated_at.desc()).limit(4)):
            d["recent_workspaces"].append({"id": str(w.id), "title": w.title, "items": len(w.items)})
    return d
