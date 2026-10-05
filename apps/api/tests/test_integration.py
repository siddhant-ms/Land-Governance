"""End-to-end flows from the brief: Question->Search->Evidence->RAG->Citation and Scenario->Parameters->Simulation->Results->Save."""
from tests.conftest import API, QUESTION


def test_flow_question_to_citation_to_workspace(client, researcher):
    hits = client.post(f"{API}/search", json={"query": QUESTION}).json()
    assert hits["results"]
    ans = client.post(f"{API}/research/ask", json={"question": QUESTION}).json()
    assert ans["claims"] and ans["sources"]
    src = ans["sources"][0]
    chunk = client.get(f"{API}/documents/{src['document_id']}/chunks/{src['chunk_id']}").json()
    assert chunk["chunk"]["text"] == src["passage"] and chunk["document"]["title"] == src["title"]
    ws = client.post(f"{API}/workspaces", headers=researcher, json={"title": "Flow 1", "research_question": QUESTION}).json()
    for s in ans["sources"][:3]:
        client.post(f"{API}/workspaces/{ws['id']}/items", headers=researcher, json={
            "item_type": "citation", "ref_id": s["chunk_id"], "title": s["title"],
            "payload": {k: s[k] for k in ("title", "organization", "publication_date", "page", "passage", "is_demo")}})
    client.post(f"{API}/workspaces/{ws['id']}/items", headers=researcher, json={"item_type": "answer", "title": "Answer", "payload": {"claims": ans["claims"]}})
    brief = client.get(f"{API}/workspaces/{ws['id']}/brief", headers=researcher).json()["content"]
    assert "## Cited findings" in brief and ans["claims"][0]["text"][:40] in brief and "## Sources" in brief


def test_flow_map_region_to_scenario_to_save(client, researcher):
    # map -> region
    layer = client.get(f"{API}/gis/layers/digitization_coverage?state=KA").json()
    assert layer["features"]
    region_id = next(f["properties"]["region_id"] for f in layer["features"] if f["properties"]["name"] == "Mysuru")
    profile = client.get(f"{API}/regions/{region_id}").json()
    sc_short = profile["scenario_shortcut"]
    # scenario lab: baseline -> change one parameter -> run
    base = client.get(f"{API}/models/{sc_short['model_id']}/baseline?region_id={region_id}").json()["values"]
    params = {**base, "target_coverage": 90.0}
    sc = client.post(f"{API}/scenarios", headers=researcher, json={"model_id": sc_short["model_id"], "region_id": region_id,
                                                                    "name": "Mysuru to 90%", "parameters": params}).json()
    run = client.post(f"{API}/scenarios/{sc['id']}/run", headers=researcher).json()
    res = run["result"]
    wl = next(o for o in res["outputs"] if o["key"] == "administrative_workload_index")
    assert wl["scenario"] < wl["baseline"] and wl["delta_pct"] < 0
    assert res["baseline_context"]["region"]["name"] == "Mysuru" and res["baseline_context"]["is_demo"]
    assert res["sensitivity"]["target_coverage"]["points"] and res["limitations"] and res["assumptions"]
    # save to workspace
    ws = client.post(f"{API}/workspaces", headers=researcher, json={"title": "Flow 2"}).json()
    saved = client.post(f"{API}/workspaces/{ws['id']}/items", headers=researcher, json={
        "item_type": "scenario", "ref_id": sc["id"], "title": sc["name"],
        "payload": {"run_id": run["run_id"], "outputs": res["outputs"], "model_name": res["model"]["name"],
                    "model_version": res["model"]["version"], "input_hash": res["hashes"]["input_hash"]}})
    assert saved.status_code == 201
    brief = client.get(f"{API}/workspaces/{ws['id']}/brief", headers=researcher).json()["content"]
    assert "Mysuru to 90%" in brief and res["hashes"]["input_hash"] in brief
