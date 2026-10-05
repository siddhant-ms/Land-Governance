import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import not_found
from app.core.security import optional_user, role_of
from app.models import Indicator, Observation, Region, User
from app.services.gis import service as gis
from app.services.simulation.service import region_value

router = APIRouter(tags=["gis"])


def _region(db: Session, rid: str) -> Region:
    try:
        r = db.get(Region, uuid.UUID(rid))
    except ValueError:
        r = None
    r = r or db.scalar(select(Region).where((Region.district_code == rid) | ((Region.state_code == rid) & (Region.level == "state"))))
    if not r:
        raise not_found("Region")
    return r


@router.get("/regions")
def regions(level: str | None = Query(None, pattern="^(state|district)$"), state: str | None = None, db: Session = Depends(get_db)):
    q = select(Region).order_by(Region.state_code, Region.name)
    if level:
        q = q.where(Region.level == level)
    if state:
        q = q.where(Region.state_code == state)
    return [{"id": str(r.id), "name": r.name, "level": r.level, "state_code": r.state_code, "district_code": r.district_code,
             "centroid": [r.centroid_lon, r.centroid_lat], "schematic": r.is_schematic} for r in db.scalars(q)]


@router.get("/regions/{region_id}")
def region(region_id: str, db: Session = Depends(get_db), user: User | None = Depends(optional_user)):
    return gis.region_profile(db, _region(db, region_id), role_of(user))


@router.get("/indicators")
def indicators(db: Session = Depends(get_db), user: User | None = Depends(optional_user)):
    return [gis.indicator_dict(db, i, role_of(user)) for i in db.scalars(select(Indicator).order_by(Indicator.category, Indicator.name))]


@router.get("/indicators/{ident}/observations")
def observations(ident: str, region_id: str | None = None, state: str | None = None, period: int | None = None,
                 db: Session = Depends(get_db), user: User | None = Depends(optional_user)):
    role = role_of(user)
    ind = gis.get_indicator(db, ident, role)
    q = select(Observation, Region).join(Region, Region.id == Observation.region_id).where(Observation.indicator_id == ind.id)
    if region_id:
        q = q.where(Region.id == _region(db, region_id).id)
    if state:
        q = q.where(Region.state_code == state)
    if period:
        q = q.where(Observation.period == period)
    rows = db.execute(q.order_by(Observation.period, Region.name).limit(2000)).all()
    return {"indicator": gis.indicator_dict(db, ind, role),
            "observations": [{"region_id": str(r.id), "region": r.name, "period": o.period, "value": o.value} for o, r in rows]}


@router.get("/gis/layers/{ident}")
def layer(ident: str, period: int | None = None, state: str | None = None, level: str = Query("district", pattern="^(state|district)$"),
          db: Session = Depends(get_db), user: User | None = Depends(optional_user)):
    ind = gis.get_indicator(db, ident, role_of(user))
    fc = gis.layer_geojson(db, ind, period, state, "district")
    if level == "state":  # aggregate district values up to state shapes
        states = gis.boundaries_geojson(db, "state", state)
        for f in states["features"]:
            reg = db.get(Region, uuid.UUID(f["properties"]["region_id"]))
            f["properties"]["value"] = region_value(db, reg, ind, fc["meta"]["period"])
        states["meta"] = {**fc["meta"], "level": "state"}
        return states
    return fc


@router.get("/gis/boundaries")
def boundaries(level: str = Query("state", pattern="^(state|district)$"), state: str | None = None, db: Session = Depends(get_db)):
    fc = gis.boundaries_geojson(db, level, state)
    fc["meta"] = {"geometry_note": "Schematic tiles at approximate district-HQ positions — not survey or official boundaries.",
                  "label": "DEMO / SCHEMATIC BOUNDARIES"}
    return fc
