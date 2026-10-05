"""Demo geography + SYNTHETIC indicators.

Boundaries: schematic hex tiles centred on approximate district-HQ coordinates. They are NOT survey or
official boundaries. Indicator values: seeded pseudo-random, labelled DEMO / SYNTHETIC DATA everywhere.
"""
import math
import random

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DataSource, Indicator, Observation, Region

YEARS = list(range(2019, 2025))

# state_code: (name, hex circumradius in degrees, target mean 2024 digitization %, districts)
# district: (code, name, lon, lat, climate_vulnerability_base 0-1)
STATES = {
    "KA": ("Karnataka", 0.30, 62.0, [
        ("BLR", "Bengaluru Urban", 77.59, 12.97, 0.30), ("MYS", "Mysuru", 76.64, 12.30, 0.25),
        ("BGM", "Belagavi", 74.50, 15.85, 0.42), ("KLB", "Kalaburagi", 76.83, 17.33, 0.55),
        ("DWD", "Dharwad", 75.01, 15.46, 0.38), ("DKN", "Dakshina Kannada", 74.86, 12.91, 0.58),
        ("SMG", "Shivamogga", 75.57, 13.93, 0.33), ("BLY", "Ballari", 76.92, 15.14, 0.50)]),
    "MH": ("Maharashtra", 0.32, 71.0, [
        ("PUN", "Pune", 73.86, 18.52, 0.30), ("MUB", "Mumbai Suburban", 72.88, 19.08, 0.62),
        ("NAG", "Nagpur", 79.09, 21.15, 0.40), ("NSK", "Nashik", 73.79, 19.99, 0.35),
        ("AUR", "Chhatrapati Sambhajinagar", 75.34, 19.88, 0.52), ("KOP", "Kolhapur", 74.24, 16.70, 0.48),
        ("SOL", "Solapur", 75.91, 17.66, 0.56), ("AMR", "Amravati", 77.75, 20.93, 0.45)]),
    "TN": ("Tamil Nadu", 0.25, 66.0, [
        ("CHE", "Chennai", 80.27, 13.08, 0.60), ("CBE", "Coimbatore", 76.96, 11.02, 0.28),
        ("MDU", "Madurai", 78.12, 9.93, 0.45), ("TRY", "Tiruchirappalli", 78.70, 10.79, 0.40),
        ("SLM", "Salem", 78.15, 11.66, 0.35), ("TVL", "Tirunelveli", 77.70, 8.73, 0.50),
        ("VLR", "Vellore", 79.13, 12.92, 0.38), ("TNJ", "Thanjavur", 79.14, 10.79, 0.55)]),
    "OD": ("Odisha", 0.18, 48.0, [
        ("KHU", "Khordha", 85.62, 20.18, 0.66), ("CTC", "Cuttack", 85.88, 20.46, 0.70),
        ("PRI", "Puri", 85.83, 19.81, 0.78), ("GJM", "Ganjam", 84.98, 19.39, 0.72),
        ("SDG", "Sundargarh", 84.04, 22.12, 0.35), ("BLS", "Balasore", 86.93, 21.49, 0.74),
        ("KPT", "Koraput", 82.71, 18.81, 0.40), ("SBP", "Sambalpur", 83.98, 21.47, 0.38)]),
}
STATE_DISPUTE_BASE = {"KA": 100.0, "MH": 108.0, "TN": 95.0, "OD": 112.0}

DEMO_LABEL = "DEMO / SYNTHETIC DATA — generated for the prototype; not an official statistic"


def hexagon(lon: float, lat: float, r: float) -> list[list[float]]:
    # lon scaled by cos(lat) so tiles look regular on an equirectangular map
    k = 1 / math.cos(math.radians(lat))
    pts = [[round(lon + r * k * math.cos(math.radians(60 * i + 30)), 5), round(lat + r * math.sin(math.radians(60 * i + 30)), 5)]
           for i in range(6)]
    return pts + [pts[0]]


def convex_hull(points: list[tuple[float, float]]) -> list[list[float]]:
    pts = sorted(set(points))

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    hull = lower[:-1] + upper[:-1]
    return [list(p) for p in hull] + [list(hull[0])]


def _sources(db: Session) -> dict[str, DataSource]:
    defs = [
        ("demo_indicators", "DEMO synthetic district indicators (2019-2024)", "synthetic", True,
         "Seeded pseudo-random values with plausible trends. No relationship to real district statistics. "
         "Digitization coverage for each state is calibrated so the 2024 state mean equals the demo baseline."),
        ("demo_boundaries", "DEMO schematic district tiles", "synthetic", True,
         "Hex tiles at approximate district-HQ coordinates. Not survey/official boundaries; adjacency is not implied."),
        ("demo_model_calibration", "DEMO simulation coefficients", "synthetic", True,
         "Illustrative coefficients chosen for explainability. Require domain-expert calibration before real use."),
    ]
    out: dict[str, DataSource] = {}
    for key, name, kind, is_demo, desc in defs:
        ds = db.scalar(select(DataSource).where(DataSource.key == key))
        if not ds:
            ds = DataSource(key=key, name=name, kind=kind, is_demo=is_demo, description=desc,
                            organization="SIH26019 Prototype Team", license="Demo use only")
            db.add(ds)
        out[key] = ds
    db.flush()
    return out


INDICATORS = [
    # key, name, unit, category, higher_is_better, legend_min, legend_max, access, description
    ("digitization_coverage", "Land-record digitization coverage", "%", "governance", True, 0, 100, "public",
     "Share of land records digitized and available online (demo value)."),
    ("dispute_pressure_index", "Land-dispute pressure index", "index (100 = demo reference)", "governance", False, 60, 150,
     "public", "Indexed pending land-dispute pressure (demo value). 100 = demo reference level."),
    ("climate_vulnerability_index", "Climate vulnerability index", "0-1", "climate", False, 0, 1, "public",
     "Composite climate exposure/vulnerability score (demo value)."),
    ("agri_land_share", "Agricultural land share", "% of area", "land_use", None, 20, 90, "public",
     "Share of district area under agricultural use (demo value)."),
    ("mutation_processing_days", "Mean mutation processing time", "days", "governance", False, 5, 60, "public",
     "Average days to complete an uncontested mutation (demo value)."),
    ("pending_mutation_per_1000", "Pending mutation cases per 1,000 records", "cases / 1,000", "governance", False, 10, 160,
     "restricted", "PROTECTED dataset (analyst+): pending mutation caseload (demo value)."),
]


def seed_gis(db: Session) -> dict:
    if db.scalar(select(Region).limit(1)):
        return {"skipped": True}
    src = _sources(db)
    inds: dict[str, Indicator] = {}
    for key, name, unit, cat, hib, lo, hi, access, desc in INDICATORS:
        ind = Indicator(key=key, name=name, unit=unit, category=cat, higher_is_better=bool(hib) if hib is not None else True,
                        legend_min=lo, legend_max=hi, access_level=access, description=desc,
                        source_definition=DEMO_LABEL, data_source_id=src["demo_indicators"].id)
        db.add(ind)
        inds[key] = ind
    db.flush()

    rng = random.Random(26019)
    districts_by_state: dict[str, list[Region]] = {}
    for scode, (sname, radius, target, dlist) in STATES.items():
        polys, dregions = [], []
        for code, name, lon, lat, _ in dlist:
            ring = hexagon(lon, lat, radius)
            polys += [tuple(p) for p in ring]
            dregions.append(Region(level="district", state_code=scode, district_code=f"{scode}-{code}", name=name,
                                   geometry={"type": "Polygon", "coordinates": [ring]}, centroid_lon=lon,
                                   centroid_lat=lat, is_schematic=True))
        hull = convex_hull(polys)
        state = Region(level="state", state_code=scode, district_code=None, name=sname,
                       geometry={"type": "Polygon", "coordinates": [hull]},
                       centroid_lon=sum(p[0] for p in hull[:-1]) / len(hull[:-1]),
                       centroid_lat=sum(p[1] for p in hull[:-1]) / len(hull[:-1]), is_schematic=True)
        db.add(state)
        db.flush()
        for r in dregions:
            r.parent_id = state.id
            db.add(r)
        db.flush()
        districts_by_state[scode] = dregions

        # --- synthetic observations ---
        speed = {r.district_code: rng.uniform(2.5, 5.5) for r in dregions}
        start = {r.district_code: rng.uniform(15, 45) for r in dregions}
        raw = {(r.district_code, y): start[r.district_code] + speed[r.district_code] * (y - 2019) + rng.gauss(0, 1.2)
               for r in dregions for y in YEARS}
        shift = target - sum(raw[(r.district_code, 2024)] for r in dregions) / len(dregions)
        for (code, name, _, _, clim), reg in zip([(d[0], d[1], d[2], d[3], d[4]) for d in dlist], dregions):
            dc = reg.district_code
            disp_off = rng.uniform(-14, 14)
            agri0 = rng.uniform(42, 78)
            days0 = rng.uniform(22, 55)
            pend0 = rng.uniform(60, 150)
            for y in YEARS:
                t = y - 2019
                vals = {
                    "digitization_coverage": max(3.0, min(98.0, raw[(dc, y)] + shift)),
                    "dispute_pressure_index": STATE_DISPUTE_BASE[scode] + disp_off + rng.gauss(0, 2.0) - 0.6 * t,
                    "climate_vulnerability_index": max(0.05, min(0.95, clim + 0.006 * t + rng.gauss(0, 0.01))),
                    "agri_land_share": agri0 - 0.35 * t + rng.gauss(0, 0.3),
                    "mutation_processing_days": max(6.0, days0 - 2.4 * t * (speed[dc] / 4) + rng.gauss(0, 1.0)),
                    "pending_mutation_per_1000": max(10.0, pend0 - 4.0 * t + rng.gauss(0, 3.0)),
                }
                for k, v in vals.items():
                    db.add(Observation(indicator_id=inds[k].id, region_id=reg.id, period=y, value=round(v, 3),
                                       source_id=src["demo_indicators"].id))
    db.commit()
    return {"regions": db.query(Region).count(), "observations": db.query(Observation).count()}
