"""Explainable scenario engine: 'normalized_index' model family.

Pure functions, no I/O. Everything a result shows (inputs, intermediate steps, formulas, coefficients) is returned
so the UI can render the full calculation. Same inputs + same model definition => identical outputs and hashes.
"""
import copy
import hashlib
import json

DISCLAIMER = "This is a scenario estimate, not a guaranteed real-world outcome."
RANGE_MESSAGE = ("This scenario could not be calculated because the selected parameter combination is outside the "
                 "supported model range.")


class SimulationRangeError(Exception):
    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__(RANGE_MESSAGE)


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def validate_inputs(defn: dict, inputs: dict[str, float]) -> dict[str, float]:
    problems: list[str] = []
    clean: dict[str, float] = {}
    for p in defn["parameters"]:
        v = inputs.get(p["key"], p["default"])
        try:
            v = float(v)
        except (TypeError, ValueError):
            problems.append(f"{p['label']} must be a number.")
            continue
        if v != v or v in (float("inf"), float("-inf")):
            problems.append(f"{p['label']} must be finite.")
        elif not (p["min"] <= v <= p["max"]):
            problems.append(f"{p['label']} must be between {p['min']} and {p['max']} ({p['unit']}); got {v:g}.")
        clean[p["key"]] = v
    unknown = set(inputs) - {p["key"] for p in defn["parameters"]}
    if unknown:
        problems.append(f"Unknown parameter(s): {', '.join(sorted(unknown))}.")
    if not problems:
        c0, c1 = clean["current_coverage"], clean["target_coverage"]
        cap = defn["coefficients"]["max_expansion_points"]
        if c1 < c0:
            problems.append("Target coverage must be at least the current coverage (the model supports expansion only).")
        if c1 - c0 > cap:
            problems.append(f"Coverage expansion of {c1 - c0:g} points exceeds the calibrated range of {cap:g} points.")
    if problems:
        raise SimulationRangeError(problems)
    return clean


def _compute(defn: dict, x: dict[str, float]) -> dict:
    k = defn["coefficients"]
    c0, c1, cap, q = x["current_coverage"], x["target_coverage"], x["implementation_capacity"], x["data_quality"]
    p0, d0 = x["baseline_processing_pressure"], x["baseline_dispute_pressure"]
    e = c0 + (c1 - c0) * cap
    b = ((e - c0) / 100.0) * q
    pp = p0 * (1 - k["alpha_processing"] * b)
    w = p0 * (1 - k["alpha_workload"] * b) + k["transition_burden"] * (1 - cap) * (c1 - c0) / 100.0
    d = d0 * (1 - k["alpha_dispute"] * b)
    return {"steps": {"delivered_coverage": e, "effective_benefit": b}, "coverage_gap": 100 - e,
            "processing_pressure": pp, "administrative_workload_index": w, "dispute_pressure_index": d,
            "e": e, "W": w, "D": d}


def _composite(defn: dict, e: float, w: float, d: float) -> float:
    k = defn["coefficients"]
    ref = k["index_ref_max"]
    return 100 * (k["w_coverage"] * e / 100 + k["w_workload"] * (1 - _clamp(w / ref)) + k["w_dispute"] * (1 - _clamp(d / ref)))


def outputs_for(defn: dict, x: dict[str, float]) -> dict[str, float]:
    s = _compute(defn, x)
    return {"coverage_gap": s["coverage_gap"], "processing_pressure": s["processing_pressure"],
            "administrative_workload_index": s["administrative_workload_index"],
            "dispute_pressure_index": s["dispute_pressure_index"],
            "composite_impact_index": _composite(defn, s["e"], s["W"], s["D"])}


def baseline_outputs(defn: dict, x: dict[str, float]) -> dict[str, float]:
    """Baseline = no intervention: target equals current, so b = 0 and no transition burden."""
    return outputs_for(defn, {**x, "target_coverage": x["current_coverage"]})


def canonical_hash(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def _pct(base: float, new: float) -> float | None:
    return None if abs(base) < 1e-9 else round((new - base) / abs(base) * 100, 2)


def sensitivity(defn: dict, x: dict[str, float], param: str, n: int = 9) -> dict:
    p = next(p for p in defn["parameters"] if p["key"] == param)
    lo, hi = p["min"], p["max"]
    if param == "target_coverage":
        lo, hi = x["current_coverage"], min(p["max"], x["current_coverage"] + defn["coefficients"]["max_expansion_points"])
    if param == "target_coverage":  # clean 5-point grid so the chart axis reads naturally
        start = int(lo // 5 * 5) + 5
        pts = sorted({lo, x[param], *[float(v) for v in range(start, int(hi) + 1, 5)]})
    else:
        pts = sorted({round(lo + (hi - lo) * i / (n - 1), 3) for i in range(n)} | {x[param]})
    rows = []
    for v in pts:
        o = outputs_for(defn, {**x, param: v})
        rows.append({"value": v, **{k: round(val, 3) for k, val in o.items()}})
    return {"parameter": param, "label": p["label"], "unit": p["unit"], "current": x[param], "points": rows}


def tornado(defn: dict, x: dict[str, float], rel: float = 0.10, output: str = "composite_impact_index") -> list[dict]:
    base = outputs_for(defn, x)[output]
    rows = []
    for p in defn["parameters"]:
        k = p["key"]
        lo_v, hi_v = x[k] * (1 - rel), x[k] * (1 + rel)
        lo_v, hi_v = max(p["min"], lo_v), min(p["max"], hi_v)
        res = {}
        for tag, v in (("low", lo_v), ("high", hi_v)):
            try:
                res[tag] = round(outputs_for(defn, validate_inputs(defn, {**x, k: v}))[output], 3)
            except SimulationRangeError:
                res[tag] = None
        rows.append({"parameter": k, "label": p["label"], "low_value": round(lo_v, 3), "high_value": round(hi_v, 3),
                     "low_output": res["low"], "high_output": res["high"], "base_output": round(base, 3),
                     "swing": round(abs((res["high"] if res["high"] is not None else base) -
                                        (res["low"] if res["low"] is not None else base)), 3)})
    return sorted(rows, key=lambda r: -r["swing"])


def run_model(defn: dict, raw_inputs: dict[str, float], *, baseline_meta: dict | None = None,
              baseline_values: dict[str, float] | None = None) -> dict:
    """Execute a scenario. `baseline_values` = the region-derived defaults, used to flag which inputs the user changed."""
    x = validate_inputs(defn, raw_inputs)
    base = baseline_outputs(defn, x)
    scen = outputs_for(defn, x)
    st = _compute(defn, x)["steps"]
    outs = []
    for o in defn["outputs"]:
        b, s = base[o["key"]], scen[o["key"]]
        delta = s - b
        improved = (delta > 1e-9) if o["higher_is_better"] else (delta < -1e-9)
        worsened = (delta < -1e-9) if o["higher_is_better"] else (delta > 1e-9)
        outs.append({"key": o["key"], "label": o["label"], "unit": o["unit"], "higher_is_better": o["higher_is_better"],
                     "baseline": round(b, 3), "scenario": round(s, 3), "delta": round(delta, 3),
                     "delta_pct": _pct(b, s), "direction": "improved" if improved else "worsened" if worsened else "unchanged"})
    k = defn["coefficients"]
    inputs = [{"key": p["key"], "label": p["label"], "unit": p["unit"], "value": x[p["key"]],
               "baseline_value": (baseline_values or {}).get(p["key"], p["default"]),
               "changed": abs(x[p["key"]] - (baseline_values or {}).get(p["key"], p["default"])) > 1e-9,
               "min": p["min"], "max": p["max"]} for p in defn["parameters"]]
    substituted = [
        f"e = {x['current_coverage']:g} + ({x['target_coverage']:g} - {x['current_coverage']:g}) x {x['implementation_capacity']:g} = {st['delivered_coverage']:.2f}",
        f"b = (({st['delivered_coverage']:.2f} - {x['current_coverage']:g}) / 100) x {x['data_quality']:g} = {st['effective_benefit']:.4f}",
        f"W = {x['baseline_processing_pressure']:g} x (1 - {k['alpha_workload']:g} x {st['effective_benefit']:.4f}) + {k['transition_burden']:g} x (1 - {x['implementation_capacity']:g}) x ({x['target_coverage']:g} - {x['current_coverage']:g}) / 100 = {scen['administrative_workload_index']:.2f}",
    ]
    result = {
        "disclaimer": DISCLAIMER, "is_demo_calibration": bool(defn.get("is_demo_calibration", True)),
        "inputs": inputs, "baseline_context": baseline_meta or {}, "intermediate": {k2: round(v, 4) for k2, v in st.items()},
        "outputs": outs, "equations": defn["equations"], "substituted": substituted,
        "coefficients": k, "coefficient_provenance": defn["coefficient_provenance"],
        "assumptions": defn["assumptions"], "limitations": defn["limitations"],
        "sensitivity": {p: sensitivity(defn, x, p) for p in ("target_coverage", "implementation_capacity", "data_quality")},
        "tornado": tornado(defn, x),
    }
    result["hashes"] = {"input_hash": canonical_hash({"model": defn["key"], "version": defn["version"], "inputs": x}),
                        "output_hash": canonical_hash({"outputs": outs})}
    return result


def deep_copy_definition(defn: dict) -> dict:
    return copy.deepcopy(defn)
