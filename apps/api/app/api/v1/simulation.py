import uuid

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import audit
from app.core.db import get_db
from app.core.errors import AppError, not_found
from app.core.security import require
from app.models import Region, Scenario, ScenarioRun, SimModel, User
from app.services.simulation.service import create_scenario, derive_baseline, execute_run, get_model

router = APIRouter(tags=["simulation"])


def model_out(m: SimModel, full: bool = True) -> dict:
    d = {"id": str(m.id), "key": m.key, "name": m.name, "version": m.version, "status": m.status,
         "description": m.description, "review_status": m.review_status,
         "is_demo_calibration": m.definition.get("is_demo_calibration", True)}
    if full:
        d.update({"methodology": m.methodology, "parameters": m.definition["parameters"], "outputs": m.definition["outputs"],
                  "equations": m.definition["equations"], "coefficients": m.definition["coefficients"],
                  "coefficient_provenance": m.definition["coefficient_provenance"], "assumptions": m.definition["assumptions"],
                  "limitations": m.definition["limitations"], "review_notes": m.review_notes})
    return d


@router.get("/models")
def models(db: Session = Depends(get_db), user: User | None = Depends(require("corpus.read_public"))):
    return [model_out(m) for m in db.scalars(select(SimModel).where(SimModel.status == "active").order_by(SimModel.name))]


@router.get("/models/{model_id}/baseline")
def baseline(model_id: uuid.UUID, region_id: uuid.UUID | None = None, db: Session = Depends(get_db),
             user: User | None = Depends(require("corpus.read_public"))):
    m = get_model(db, model_id)
    region = db.get(Region, region_id) if region_id else None
    if region_id and not region:
        raise not_found("Region")
    values, meta = derive_baseline(db, m.definition, region)
    return {"values": values, "context": meta}


class ScenarioIn(BaseModel):
    model_id: uuid.UUID
    name: str = Field(min_length=2, max_length=255)
    description: str = Field(default="", max_length=2000)
    region_id: uuid.UUID | None = None
    parameters: dict[str, float] = Field(default_factory=dict)


def scenario_out(s: Scenario, db: Session, runs: bool = False) -> dict:
    region = db.get(Region, s.region_id) if s.region_id else None
    d = {"id": str(s.id), "name": s.name, "description": s.description, "model_id": str(s.model_id),
         "model": {"name": s.model.name, "version": s.model.version}, "region": {"id": str(region.id), "name": region.name} if region else None,
         "parameters": {p.name: p.value for p in s.parameters}, "created_at": s.created_at.isoformat()}
    latest = db.scalar(select(ScenarioRun).where(ScenarioRun.scenario_id == s.id).order_by(ScenarioRun.created_at.desc()))
    d["latest_run_id"] = str(latest.id) if latest else None
    if latest:
        d["summary"] = [{"key": o["key"], "label": o["label"], "baseline": o["baseline"], "scenario": o["scenario"], "delta_pct": o["delta_pct"]}
                        for o in latest.output_json["outputs"]]
    return d


def owned(db: Session, sid: uuid.UUID, user: User) -> Scenario:
    s = db.get(Scenario, sid)
    if not s or s.deleted_at or (s.owner_id != user.id and user.role.name != "admin"):
        raise not_found("Scenario")  # no existence leak for other users' scenarios
    return s


@router.post("/scenarios", status_code=201)
def create(body: ScenarioIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require("scenario.run"))):
    sc = create_scenario(db, user, body.model_id, body.name, body.region_id, body.parameters, body.description)
    audit.record(db, request, user, "SCENARIO_CREATED", "scenario", sc.id, {"model": sc.model.key, "version": sc.model.version})
    return scenario_out(sc, db)


@router.get("/scenarios")
def list_scenarios(db: Session = Depends(get_db), user: User = Depends(require("scenario.run"))):
    rows = db.scalars(select(Scenario).where(Scenario.owner_id == user.id, Scenario.deleted_at.is_(None)).order_by(Scenario.created_at.desc())).all()
    return [scenario_out(s, db) for s in rows]


@router.get("/scenarios/compare")
def compare(run_ids: str = Query(..., description="comma-separated run ids (2-4)"), db: Session = Depends(get_db),
            user: User = Depends(require("scenario.run"))):
    ids = [uuid.UUID(x) for x in run_ids.split(",") if x][:4]
    if len(ids) < 2:
        raise AppError(422, "COMPARE_NEEDS_TWO", "Select at least two saved runs to compare.")
    runs = []
    for rid in ids:
        r = db.get(ScenarioRun, rid)
        sc = db.get(Scenario, r.scenario_id) if r else None
        if not r or not sc or (sc.owner_id != user.id and user.role.name != "admin"):
            raise not_found("Run")
        runs.append((r, sc))
    keys = [o["key"] for o in runs[0][0].output_json["outputs"]]
    return {"runs": [{"run_id": str(r.id), "scenario": sc.name, "model_version": r.model_version,
                      "inputs": {i["key"]: i["value"] for i in r.output_json["inputs"]}} for r, sc in runs],
            "outputs": [{"key": k, "label": next(o["label"] for o in runs[0][0].output_json["outputs"] if o["key"] == k),
                         "baseline": next(o["baseline"] for o in runs[0][0].output_json["outputs"] if o["key"] == k),
                         "values": [next((o["scenario"] for o in r.output_json["outputs"] if o["key"] == k), None) for r, _ in runs]}
                        for k in keys],
            "note": "Runs are compared on their own baselines; compare runs from the same region for like-for-like results."}


@router.get("/scenarios/{sid}")
def get_scenario(sid: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require("scenario.run"))):
    s = owned(db, sid, user)
    runs = db.scalars(select(ScenarioRun).where(ScenarioRun.scenario_id == s.id).order_by(ScenarioRun.created_at.desc())).all()
    return {**scenario_out(s, db), "runs": [{"id": str(r.id), "created_at": r.created_at.isoformat(), "model_version": r.model_version,
                                             "output_hash": r.output_hash} for r in runs]}


@router.post("/scenarios/{sid}/run")
def run(sid: uuid.UUID, request: Request, db: Session = Depends(get_db), user: User = Depends(require("scenario.run"))):
    s = owned(db, sid, user)
    r = execute_run(db, s, user)
    audit.record(db, request, user, "SCENARIO_RUN", "scenario", s.id,
                 {"run_id": str(r.id), "model_version": r.model_version, "input_hash": r.input_hash, "output_hash": r.output_hash})
    return {"run_id": str(r.id), "scenario_id": str(s.id), "created_at": r.created_at.isoformat(), "result": r.output_json}


def _run_of(db: Session, sid: uuid.UUID, rid: uuid.UUID, user: User) -> tuple[Scenario, ScenarioRun]:
    s = owned(db, sid, user)
    r = db.get(ScenarioRun, rid)
    if not r or r.scenario_id != s.id:
        raise not_found("Run")
    return s, r


@router.get("/scenarios/{sid}/runs/{rid}")
def get_run(sid: uuid.UUID, rid: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require("scenario.run"))):
    _, r = _run_of(db, sid, rid, user)
    return {"run_id": str(r.id), "scenario_id": str(sid), "created_at": r.created_at.isoformat(), "result": r.output_json}


def scenario_markdown(s: Scenario, r: ScenarioRun) -> str:
    res = r.output_json
    L = [f"# Scenario brief: {s.name}", "", f"*Model:* {res['model']['name']} v{res['model']['version']}  ",
         f"*Run:* {r.id}  *Generated:* {r.created_at.isoformat()}  ", f"*Input hash:* `{r.input_hash}`  *Output hash:* `{r.output_hash}`", "",
         f"> {res['disclaimer']}" + ("  \n> **DEMO / SYNTHETIC calibration and data.**" if res.get("is_demo_calibration") else ""), "",
         "## Inputs", "", "| Parameter | Value | Baseline |", "|---|---|---|"]
    L += [f"| {i['label']} ({i['unit']}) | {i['value']:g} | {i['baseline_value']:g} |" for i in res["inputs"]]
    L += ["", "## Baseline vs scenario", "", "| Indicator | Baseline | Scenario | Change |", "|---|---|---|---|"]
    L += [f"| {o['label']} | {o['baseline']:g} | {o['scenario']:g} | {o['delta_pct'] if o['delta_pct'] is not None else 'n/a'}% |" for o in res["outputs"]]
    L += ["", "## Equations", ""] + [f"- {e['formula']}" for e in res["equations"]]
    L += ["", "## Coefficient provenance", ""] + [f"- **{k}** = {res['coefficients'][k]}: {v}" for k, v in res["coefficient_provenance"].items()]
    L += ["", "## Baseline data", "", res["baseline_context"].get("note", "")]
    L += ["", "## Assumptions", ""] + [f"- {a}" for a in res["assumptions"]]
    L += ["", "## Limitations", ""] + [f"- {a}" for a in res["limitations"]]
    return "\n".join(L)


@router.get("/scenarios/{sid}/runs/{rid}/export")
def export_run(sid: uuid.UUID, rid: uuid.UUID, request: Request, db: Session = Depends(get_db),
               user: User = Depends(require("scenario.export"))):
    s, r = _run_of(db, sid, rid, user)
    audit.record(db, request, user, "SCENARIO_EXPORTED", "scenario", s.id, {"run_id": str(r.id), "format": "markdown"})
    return {"filename": f"scenario-{s.id}.md", "content_type": "text/markdown", "content": scenario_markdown(s, r)}
