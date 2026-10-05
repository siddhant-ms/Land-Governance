import json
from pathlib import Path

import pytest

from app.services.simulation.engine import SimulationRangeError, run_model, validate_inputs
from tests.conftest import API

DEFN = json.loads((Path(__file__).parents[3] / "data/seed/models/land_record_digitization_v1.json").read_text())
BASE = {"current_coverage": 62, "target_coverage": 80, "implementation_capacity": 1.0, "data_quality": 1.0}


def out(r, key):
    return next(o for o in r["outputs"] if o["key"] == key)


def test_prd_example_workload_100_to_about_84():
    r = run_model(DEFN, BASE)
    w = out(r, "administrative_workload_index")
    assert w["baseline"] == 100 and w["scenario"] == pytest.approx(83.8, abs=0.01) and w["delta_pct"] == pytest.approx(-16.2, abs=0.05)
    assert out(r, "coverage_gap")["baseline"] == 38 and out(r, "coverage_gap")["scenario"] == 20
    assert out(r, "dispute_pressure_index")["scenario"] == pytest.approx(91.0, abs=0.01)
    assert out(r, "composite_impact_index")["baseline"] == pytest.approx(54.8, abs=0.01)


def test_zero_change_scenario_equals_baseline():
    r = run_model(DEFN, {**BASE, "target_coverage": 62})
    assert all(o["delta"] == 0 and o["direction"] == "unchanged" for o in r["outputs"])


def test_capacity_and_quality_monotonic():
    lo = run_model(DEFN, {**BASE, "implementation_capacity": 0.4})
    hi = run_model(DEFN, {**BASE, "implementation_capacity": 1.0})
    assert out(lo, "administrative_workload_index")["scenario"] > out(hi, "administrative_workload_index")["scenario"]
    assert out(lo, "composite_impact_index")["scenario"] < out(hi, "composite_impact_index")["scenario"]
    lq = run_model(DEFN, {**BASE, "data_quality": 0.5})
    assert out(lq, "dispute_pressure_index")["scenario"] > out(hi, "dispute_pressure_index")["scenario"]


def test_transition_burden_can_worsen_workload_at_low_capacity():
    r = run_model(DEFN, {**BASE, "target_coverage": 90, "implementation_capacity": 0.1, "data_quality": 0.5})
    assert out(r, "administrative_workload_index")["direction"] == "worsened"


@pytest.mark.parametrize("bad", [
    {"target_coverage": 50}, {"target_coverage": 101}, {"current_coverage": 20, "target_coverage": 100},
    {"implementation_capacity": 0.0}, {"data_quality": 1.5}, {"baseline_dispute_pressure": 10}, {"target_coverage": "abc"},
    {"mystery": 1}, {"target_coverage": float("nan")},
])
def test_out_of_range_rejected(bad):
    with pytest.raises(SimulationRangeError):
        validate_inputs(DEFN, {**BASE, **bad})


def test_boundaries_accepted():
    for v in ({"target_coverage": 100, "current_coverage": 40}, {"target_coverage": 62}, {"implementation_capacity": 0.1}, {"data_quality": 0.5}):
        run_model(DEFN, {**BASE, **v})


def test_deterministic_hashes_and_sensitivity():
    a, b = run_model(DEFN, BASE), run_model(DEFN, BASE)
    assert a["hashes"] == b["hashes"] and run_model(DEFN, {**BASE, "target_coverage": 81})["hashes"] != a["hashes"]
    pts = a["sensitivity"]["target_coverage"]["points"]
    vals = [p["composite_impact_index"] for p in pts]
    assert vals == sorted(vals) and pts[0]["value"] == 62 and any(p["value"] == 80 for p in pts)
    assert a["tornado"][0]["swing"] >= a["tornado"][-1]["swing"]


def test_result_is_fully_transparent():
    r = run_model(DEFN, BASE)
    for k in ("inputs", "outputs", "equations", "substituted", "coefficient_provenance", "assumptions", "limitations", "disclaimer"):
        assert r[k]
    assert "not a guaranteed real-world outcome" in r["disclaimer"] and r["is_demo_calibration"] is True
    assert all(v.startswith("SYNTHETIC DEMO CALIBRATION") or "Analyst-chosen" in v or "Normalization" in v or "Calibrated" in v
               for v in r["coefficient_provenance"].values())


# ---- API ----
@pytest.fixture(scope="module")
def ka(client):
    return next(r for r in client.get(f"{API}/regions?level=state").json() if r["state_code"] == "KA")


@pytest.fixture(scope="module")
def model(client):
    return client.get(f"{API}/models").json()[0]


def test_models_catalog_public(client, model):
    assert model["key"] == "land_record_digitization" and model["parameters"] and model["coefficient_provenance"]


def test_baseline_endpoint_uses_region_data(client, model, ka):
    b = client.get(f"{API}/models/{model['id']}/baseline?region_id={ka['id']}").json()
    assert round(b["values"]["current_coverage"]) == 62 and b["context"]["is_demo"] and b["context"]["sources"]


def test_create_run_get_and_compare(client, researcher, model, ka):
    base = client.get(f"{API}/models/{model['id']}/baseline?region_id={ka['id']}").json()["values"]
    ids = []
    for name, target in (("s80", 80), ("s90", 90)):
        sc = client.post(f"{API}/scenarios", headers=researcher, json={"model_id": model["id"], "name": name, "region_id": ka["id"],
                                                                        "parameters": {**base, "target_coverage": target}})
        assert sc.status_code == 201, sc.text
        run = client.post(f"{API}/scenarios/{sc.json()['id']}/run", headers=researcher)
        assert run.status_code == 200, run.text
        res = run.json()["result"]
        assert res["model"]["version"] == model["version"] and res["hashes"]["input_hash"]
        assert res["inputs"][1]["changed"] is True and res["inputs"][0]["changed"] is False
        fetched = client.get(f"{API}/scenarios/{sc.json()['id']}/runs/{run.json()['run_id']}", headers=researcher).json()
        assert fetched["result"]["hashes"] == res["hashes"]
        ids.append(run.json()["run_id"])
    cmp = client.get(f"{API}/scenarios/compare?run_ids={','.join(ids)}", headers=researcher).json()
    comp = next(o for o in cmp["outputs"] if o["key"] == "composite_impact_index")
    assert comp["values"][1] > comp["values"][0]
    assert client.get(f"{API}/scenarios/compare?run_ids={ids[0]}", headers=researcher).status_code == 422


def test_out_of_range_api_error_message(client, researcher, model, ka):
    sc = client.post(f"{API}/scenarios", headers=researcher, json={"model_id": model["id"], "name": "bad", "region_id": ka["id"],
                                                                    "parameters": {"current_coverage": 62, "target_coverage": 40}}).json()
    r = client.post(f"{API}/scenarios/{sc['id']}/run", headers=researcher)
    assert r.status_code == 422 and r.json()["error"]["code"] == "SIMULATION_OUT_OF_RANGE"
    assert "outside the supported model range" in r.json()["error"]["message"] and r.json()["error"]["details"]["problems"]


def test_scenarios_are_private_and_export_needs_analyst(client, researcher, analyst, model, ka):
    sc = client.post(f"{API}/scenarios", headers=researcher, json={"model_id": model["id"], "name": "mine", "region_id": ka["id"], "parameters": {}}).json()
    run = client.post(f"{API}/scenarios/{sc['id']}/run", headers=researcher).json()
    assert client.get(f"{API}/scenarios/{sc['id']}", headers=analyst).status_code == 404  # other user's scenario
    assert client.post(f"{API}/scenarios", json={"model_id": model["id"], "name": "x", "parameters": {}}).status_code == 401
    url = f"{API}/scenarios/{sc['id']}/runs/{run['run_id']}/export"
    assert client.get(url, headers=researcher).status_code == 403
    # analyst exports their own run
    sc2 = client.post(f"{API}/scenarios", headers=analyst, json={"model_id": model["id"], "name": "an", "region_id": ka["id"], "parameters": {}}).json()
    run2 = client.post(f"{API}/scenarios/{sc2['id']}/run", headers=analyst).json()
    exp = client.get(f"{API}/scenarios/{sc2['id']}/runs/{run2['run_id']}/export", headers=analyst)
    assert exp.status_code == 200 and "not a guaranteed real-world outcome" in exp.json()["content"] and "Coefficient provenance" in exp.json()["content"]


def test_model_update_creates_new_version_and_validates(client, admin, expert, researcher):
    m = client.get(f"{API}/admin/models", headers=admin).json()
    active = next(x for x in m if x["status"] == "active")
    assert client.patch(f"{API}/admin/models/{active['id']}", headers=admin, json={"coefficients": {"w_coverage": 0.9}, "change_note": "weights test"}).status_code == 422
    assert client.patch(f"{API}/admin/models/{active['id']}", headers=expert, json={"coefficients": {"alpha_dispute": 0.4}, "change_note": "nope nope"}).status_code == 403
    r = client.patch(f"{API}/admin/models/{active['id']}", headers=admin, json={"coefficients": {"alpha_dispute": 0.4}, "change_note": "expert recalibration test"})
    assert r.status_code == 200 and r.json()["version"] == "1.0.1"
    m2 = client.get(f"{API}/admin/models", headers=admin).json()
    assert {x["version"]: x["status"] for x in m2 if x["key"] == active["key"]} == {"1.0.0": "deprecated", "1.0.1": "active"}
    assert "expert recalibration" in next(x for x in m2 if x["version"] == "1.0.1")["coefficient_provenance"]["alpha_dispute"]
    rv = client.post(f"{API}/admin/models/{r.json()['id']}/review", headers=expert, json={"status": "needs_changes", "notes": "check dispute coefficient"})
    assert rv.status_code == 200
    assert client.post(f"{API}/admin/models/{r.json()['id']}/review", headers=researcher, json={"status": "rejected", "notes": "no rights here"}).status_code == 403
