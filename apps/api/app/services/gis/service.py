import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError, not_found
from app.core.security import role_has
from app.models import DataSource, Indicator, Observation, Region, SimModel
from app.services.retrieval.search import search_evidence
from app.services.retrieval.serialize import doc_summary
from app.services.retrieval.types import SearchFilters
from app.services.simulation.service import derive_baseline, latest_period, region_value

DEMO_BADGE = "DEMO / SYNTHETIC DATA"


def indicator_dict(db: Session, ind: Indicator, role: str) -> dict:
    ds = db.get(DataSource, ind.data_source_id) if ind.data_source_id else None
    locked = ind.access_level == "restricted" and not role_has(role, "data.restricted")
    periods = [p for (p,) in db.execute(select(Observation.period).where(Observation.indicator_id == ind.id).distinct().order_by(Observation.period))]
    return {"id": str(ind.id), "key": ind.key, "name": ind.name, "unit": ind.unit, "category": ind.category,
            "description": ind.description, "higher_is_better": ind.higher_is_better, "legend": [ind.legend_min, ind.legend_max],
            "access_level": ind.access_level, "locked": locked, "periods": periods,
            "source": {"name": ds.name, "description": ds.description, "is_demo": ds.is_demo, "url": ds.url,
                       "license": ds.license} if ds else None,
            "is_demo": ds.is_demo if ds else True, "demo_label": DEMO_BADGE if (ds is None or ds.is_demo) else None}


def get_indicator(db: Session, ident: str, role: str, *, enforce: bool = True) -> Indicator:
    ind = None
    try:
        ind = db.get(Indicator, uuid.UUID(ident))
    except ValueError:
        pass
    ind = ind or db.scalar(select(Indicator).where(Indicator.key == ident))
    if not ind:
        raise not_found("Indicator")
    if enforce and ind.access_level == "restricted" and not role_has(role, "data.restricted"):
        raise AppError(403, "RESTRICTED_DATASET", "This dataset is restricted to authorized users (analyst, expert or admin).",
                       {"indicator": ind.key})
    return ind


def layer_geojson(db: Session, ind: Indicator, period: int | None, state_code: str | None, level: str = "district") -> dict:
    period = period or latest_period(db, ind.id)
    q = (select(Region, Observation.value).join(Observation, (Observation.region_id == Region.id) &
         (Observation.indicator_id == ind.id) & (Observation.period == period), isouter=True)
         .where(Region.level == level))
    if state_code:
        q = q.where(Region.state_code == state_code)
    feats = []
    for reg, val in db.execute(q).all():
        feats.append({"type": "Feature", "geometry": reg.geometry, "properties": {
            "region_id": str(reg.id), "name": reg.name, "state_code": reg.state_code, "district_code": reg.district_code,
            "level": reg.level, "value": val, "schematic": reg.is_schematic}})
    d = indicator_dict(db, ind, "admin")
    return {"type": "FeatureCollection", "features": feats,
            "meta": {"indicator": {k: d[k] for k in ("key", "name", "unit", "legend", "higher_is_better", "source", "is_demo", "demo_label")},
                     "period": period, "periods": d["periods"], "level": level,
                     "geometry_note": "Schematic tiles at approximate district-HQ positions — not survey or official boundaries."}}


def boundaries_geojson(db: Session, level: str, state_code: str | None) -> dict:
    q = select(Region).where(Region.level == level)
    if state_code:
        q = q.where(Region.state_code == state_code)
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": r.geometry, "properties": {
            "region_id": str(r.id), "name": r.name, "state_code": r.state_code, "district_code": r.district_code,
            "level": r.level, "schematic": r.is_schematic}} for r in db.scalars(q)]}


def region_profile(db: Session, region: Region, role: str) -> dict:
    inds = db.scalars(select(Indicator).order_by(Indicator.category, Indicator.name)).all()
    rows = []
    for ind in inds:
        d = indicator_dict(db, ind, role)
        if d["locked"]:
            rows.append({**d, "latest": None, "series": [], "trend": None})
            continue
        series = []
        for p in d["periods"]:
            v = region_value(db, region, ind, p)
            if v is not None:
                series.append({"period": p, "value": round(v, 2)})
        trend = None
        if len(series) >= 2:
            a, b = series[0], series[-1]
            ch = b["value"] - a["value"]
            trend = {"from": a["period"], "to": b["period"], "change": round(ch, 2),
                     "direction": "up" if ch > 0.01 else "down" if ch < -0.01 else "flat",
                     "favourable": (ch > 0) == ind.higher_is_better if abs(ch) > 0.01 else None}
        rows.append({**d, "latest": series[-1] if series else None, "series": series, "trend": trend})
    # relevant evidence: geography-boosted search, restricted docs excluded by role inside search
    out = search_evidence(db, f"{region.name} land records digitization disputes", SearchFilters(), role, top_k=30)
    docs: dict[str, dict] = {}
    for h in out.hits:
        state_match = h.doc["state_code"] in (region.state_code, None)
        if state_match and h.document_id not in docs:
            docs[h.document_id] = {**doc_summary(h.document_id, h.doc), "relevance": round(h.relevance, 3)}
    ranked = sorted(docs.values(), key=lambda d: (d["state_code"] != region.state_code, -d["relevance"]))[:8]
    model = db.scalar(select(SimModel).where(SimModel.status == "active").order_by(SimModel.created_at))
    shortcut = None
    if model:
        vals, _ = derive_baseline(db, model.definition, region)
        shortcut = {"model_id": str(model.id), "model_name": model.name, "region_id": str(region.id),
                    "baseline_coverage": vals["current_coverage"]}
    parent = db.get(Region, region.parent_id) if region.parent_id else None
    n_districts = db.scalar(select(func.count(Region.id)).where(Region.parent_id == region.id)) if region.level == "state" else 0
    return {"region": {"id": str(region.id), "name": region.name, "level": region.level, "state_code": region.state_code,
                       "district_code": region.district_code, "schematic": region.is_schematic,
                       "parent": {"id": str(parent.id), "name": parent.name} if parent else None, "n_districts": n_districts,
                       "geometry_note": "Schematic tile — not an official boundary."},
            "indicators": rows,
            "documents": [d for d in ranked if d["document_type"] != "research_paper"],
            "research": [d for d in ranked if d["document_type"] == "research_paper"],
            "scenario_shortcut": shortcut,
            "aggregation_note": "State values are the mean of district values." if region.level == "state" else None}
