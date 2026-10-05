from tests.conftest import API, QUESTION


def search(client, q, filters=None, headers=None, k=10):
    r = client.post(f"{API}/search", json={"query": q, "filters": filters or {}, "top_k": k}, headers=headers or {})
    assert r.status_code == 200, r.text
    return r.json()


def test_demo_question_returns_relevant_docs_with_metadata(client):
    body = search(client, QUESTION)
    assert body["results"], "expected results"
    top = body["results"][0]
    for f in ("title", "organization", "publication_date", "document_type", "is_demo", "why_matched", "passages"):
        assert f in top
    assert "digitization" in top["title"].lower() or "digitization" in top["passages"][0]["snippet"].lower()
    assert top["passages"][0]["explain"]["rank_lexical"] is not None  # hybrid explanation exposed
    assert body["query_analysis"]["expansions"], "query expansion shown"


def test_hybrid_uses_both_signals_and_rrf(client):
    body = search(client, "computerisation of registry and litigation")  # no literal overlap on 'computerisation'
    ex = body["results"][0]["passages"][0]["explain"]
    assert ex["rrf"] > 0 and ex["dense_cosine"] > 0


def test_off_topic_returns_empty_state(client):
    body = search(client, "cricket world cup winners")
    assert body["results"] == [] and "No sufficiently relevant evidence" in body["empty_message"]


def test_filters_state_type_and_date(client):
    ka = search(client, "mutation records", {"states": ["KA"]})
    assert ka["results"] and all(r["state_code"] == "KA" for r in ka["results"])
    cs = search(client, "land records", {"document_types": ["case_study"]})
    assert cs["results"] and all(r["document_type"] == "case_study" for r in cs["results"])
    dated = search(client, "land records digitization", {"date_from": "2024-01-01"})
    assert dated["results"] and all(r["publication_date"] >= "2024-01-01" for r in dated["results"])
    none = search(client, "land records digitization", {"states": ["ZZ"]})
    assert none["results"] == []


def test_topic_and_org_filters(client):
    r = search(client, "records", {"topics": ["Gender and land"]})
    assert r["results"] and all("Gender and land" in x["topics"] for x in r["results"])
    r = search(client, "records", {"organizations": ["Demo Legal Studies Centre (fictional)"]})
    assert r["results"] and all(x["organization"].startswith("Demo Legal") for x in r["results"])


def test_restricted_document_hidden_from_public_visible_to_analyst(client, analyst):
    q = "pending mutation caseloads district trained data-entry staff"
    pub = search(client, q)
    assert all(r["access_level"] == "public" for r in pub["results"])
    ana = search(client, q, headers=analyst)
    assert any(r["access_level"] == "restricted" for r in ana["results"])


def test_repeat_search_is_cached(client):
    search(client, "boundary disputes drone survey")
    assert search(client, "boundary disputes drone survey")["cached"] is True


def test_validation(client):
    assert client.post(f"{API}/search", json={"query": "x"}).status_code == 422
    assert client.post(f"{API}/search", json={"query": "valid query", "top_k": 999}).status_code == 422


def test_facets(client):
    f = client.get(f"{API}/search/facets").json()
    assert "KA" in f["states"] and "case_study" in f["document_types"] and f["year_range"]


def test_sql_injection_string_is_harmless(client):
    r = client.post(f"{API}/search", json={"query": "'; DROP TABLE documents; --"})
    assert r.status_code == 200
    assert client.get(f"{API}/search/facets").json()["documents"] > 5


def test_rrf_fusion_math():
    from app.services.retrieval.search import RRF_K
    assert abs((1 / (RRF_K + 1) + 1 / (RRF_K + 3)) - (1 / 61 + 1 / 63)) < 1e-12
