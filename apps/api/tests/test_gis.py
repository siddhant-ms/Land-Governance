from tests.conftest import API


def test_indicator_catalog_labels_demo_and_locks_restricted(client, analyst):
    pub = {i["key"]: i for i in client.get(f"{API}/indicators").json()}
    assert pub["digitization_coverage"]["demo_label"] == "DEMO / SYNTHETIC DATA" and pub["digitization_coverage"]["source"]["is_demo"]
    assert pub["pending_mutation_per_1000"]["locked"] is True
    ana = {i["key"]: i for i in client.get(f"{API}/indicators", headers=analyst).json()}
    assert ana["pending_mutation_per_1000"]["locked"] is False


def test_layer_geojson_and_period(client):
    fc = client.get(f"{API}/gis/layers/digitization_coverage?state=KA&period=2022").json()
    assert fc["type"] == "FeatureCollection" and len(fc["features"]) == 8
    assert fc["meta"]["period"] == 2022 and fc["meta"]["indicator"]["is_demo"] and "not survey" in fc["meta"]["geometry_note"]
    assert all(f["properties"]["value"] is not None and f["geometry"]["type"] == "Polygon" for f in fc["features"])
    assert len(fc["meta"]["periods"]) == 6
    states = client.get(f"{API}/gis/layers/climate_vulnerability_index?level=state").json()
    assert len(states["features"]) == 4 and all(f["properties"]["value"] is not None for f in states["features"])


def test_restricted_layer_403_for_public_200_for_analyst(client, analyst):
    r = client.get(f"{API}/gis/layers/pending_mutation_per_1000")
    assert r.status_code == 403 and r.json()["error"]["code"] == "RESTRICTED_DATASET"
    assert client.get(f"{API}/indicators/pending_mutation_per_1000/observations").status_code == 403
    assert client.get(f"{API}/gis/layers/pending_mutation_per_1000", headers=analyst).status_code == 200


def test_karnataka_baseline_is_62(client):
    regs = client.get(f"{API}/regions?level=state").json()
    ka = next(r for r in regs if r["state_code"] == "KA")
    prof = client.get(f"{API}/regions/{ka['id']}").json()
    dig = next(i for i in prof["indicators"] if i["key"] == "digitization_coverage")
    assert round(dig["latest"]["value"]) == 62 and dig["trend"]["direction"] == "up" and len(dig["series"]) == 6


def test_region_profile_contents(client, analyst):
    d = next(r for r in client.get(f"{API}/regions?level=district&state=KA").json() if r["name"] == "Mysuru")
    p = client.get(f"{API}/regions/{d['id']}").json()
    assert p["region"]["schematic"] and p["scenario_shortcut"]["region_id"] == d["id"]
    assert p["documents"] or p["research"]
    locked = next(i for i in p["indicators"] if i["key"] == "pending_mutation_per_1000")
    assert locked["locked"] and locked["latest"] is None
    pa = client.get(f"{API}/regions/{d['id']}", headers=analyst).json()
    assert next(i for i in pa["indicators"] if i["key"] == "pending_mutation_per_1000")["latest"] is not None


def test_unknown_region_404(client):
    assert client.get(f"{API}/regions/00000000-0000-0000-0000-000000000000").status_code == 404
