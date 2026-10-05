"""DB-facing simulation service: model registry sync, region-derived baselines, scenario persistence."""
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import REPO_ROOT
from app.core.errors import AppError, not_found
from app.models import DataSource, Indicator, Observation, Region, Scenario, ScenarioParameter, ScenarioRun, SimModel, User
from app.services.simulation.engine import RANGE_MESSAGE, SimulationRangeError, run_model

MODEL_DIR = REPO_ROOT / "data" / "seed" / "models"


def sync_models_from_files(db: Session, directory: Path = MODEL_DIR) -> int:
    n = 0
    for f in sorted(directory.glob("*.json")):
        d = json.loads(f.read_text())
        if db.scalar(select(SimModel).where(SimModel.key == d["key"], SimModel.version == d["version"])):
            continue
        db.add(SimModel(key=d["key"], name=d["name"], version=d["version"], description=d["description"],
                        methodology=d["methodology"], status=d.get("status", "active"), definition=d))
        n += 1
    db.commit()
    return n


def latest_period(db: Session, indicator_id: uuid.UUID) -> int | None:
    return db.scalar(select(func.max(Observation.period)).where(Observation.indicator_id == indicator_id))


def region_value(db: Session, region: Region, indicator: Indicator, period: int) -> float | None:
    """District: its observation. State: mean over its districts (documented aggregation)."""
    if region.level == "district":
        return db.scalar(select(Observation.value).where(Observation.indicator_id == indicator.id,
                                                         Observation.region_id == region.id, Observation.period == period))
    return db.scalar(select(func.avg(Observation.value)).join(Region, Region.id == Observation.region_id)
                     .where(Observation.indicator_id == indicator.id, Observation.period == period,
                            Region.state_code == region.state_code, Region.level == "district"))


def derive_baseline(db: Session, defn: dict, region: Region | None) -> tuple[dict[str, float], dict]:
    """Baseline values (parameter defaults) from the region's latest observations + provenance metadata."""
    values = {p["key"]: float(p["default"]) for p in defn["parameters"]}
    meta: dict = {"region": None, "sources": [], "note": "Model defaults (no region selected)."}
    if region is None:
        return values, meta
    sources = []
    is_demo = False
    period = None
    for p in defn["parameters"]:
        key = p.get("baseline_indicator")
        if not key:
            continue
        ind = db.scalar(select(Indicator).where(Indicator.key == key))
        if not ind:
            continue
        period = latest_period(db, ind.id)
        v = region_value(db, region, ind, period) if period else None
        if v is None:
            continue
        if key == "mutation_processing_days":
            ref = db.scalar(select(func.avg(Observation.value)).join(Region, Region.id == Observation.region_id)
                            .where(Observation.indicator_id == ind.id, Observation.period == period, Region.level == "district"))
            v = v / ref * 100.0  # index: 100 = mean across all demo districts
        values[p["key"]] = round(float(v), 2)
        ds = db.get(DataSource, ind.data_source_id) if ind.data_source_id else None
        is_demo = is_demo or (ds.is_demo if ds else True)
        sources.append({"parameter": p["key"], "indicator": ind.name, "period": period,
                        "source": ds.name if ds else "unknown", "is_demo": ds.is_demo if ds else True})
    meta = {"region": {"id": str(region.id), "name": region.name, "level": region.level, "state_code": region.state_code},
            "period": period, "sources": sources, "is_demo": is_demo,
            "note": ("Baselines are the region's latest observations. "
                     + ("DEMO / SYNTHETIC DATA. " if is_demo else "")
                     + ("State values are the mean of its districts. " if region.level == "state" else "")
                     + "Processing pressure is mutation days indexed to the all-district mean (=100).")}
    return values, meta


def get_model(db: Session, model_id: uuid.UUID) -> SimModel:
    m = db.get(SimModel, model_id)
    if not m:
        raise not_found("Model")
    return m


def create_scenario(db: Session, owner: User, model_id: uuid.UUID, name: str, region_id: uuid.UUID | None,
                    params: dict[str, float], description: str = "") -> Scenario:
    model = get_model(db, model_id)
    if model.status != "active":
        raise AppError(409, "MODEL_NOT_ACTIVE", "This model version is not active.")
    if region_id and not db.get(Region, region_id):
        raise not_found("Region")
    sc = Scenario(model_id=model.id, owner_id=owner.id, region_id=region_id, name=name, description=description)
    sc.parameters = [ScenarioParameter(name=k, value=float(v)) for k, v in params.items()]
    db.add(sc)
    db.commit()
    return sc


def execute_run(db: Session, scenario: Scenario, actor: User) -> ScenarioRun:
    model = scenario.model
    region = db.get(Region, scenario.region_id) if scenario.region_id else None
    baseline_values, meta = derive_baseline(db, model.definition, region)
    inputs = {p.name: p.value for p in scenario.parameters}
    try:
        # "changed" is judged against the true baseline: no intervention, i.e. target coverage == current coverage
        reference = {**baseline_values, "target_coverage": baseline_values["current_coverage"]}
        result = run_model(model.definition, inputs, baseline_meta=meta, baseline_values=reference)
    except SimulationRangeError as e:
        raise AppError(422, "SIMULATION_OUT_OF_RANGE", RANGE_MESSAGE, {"problems": e.problems}) from e
    result["model"] = {"id": str(model.id), "key": model.key, "name": model.name, "version": model.version,
                       "review_status": model.review_status}
    result["scenario"] = {"id": str(scenario.id), "name": scenario.name}
    run = ScenarioRun(scenario_id=scenario.id, model_version=model.version, input_hash=result["hashes"]["input_hash"],
                      output_hash=result["hashes"]["output_hash"], output_json=result, created_by=actor.id,
                      created_at=datetime.now(UTC))
    db.add(run)
    db.commit()
    return run
