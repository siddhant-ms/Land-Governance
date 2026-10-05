from sqlalchemy import select

from app.models import AuditEvent
from tests.conftest import API, QUESTION


def test_workspace_crud_and_isolation(client, researcher, analyst):
    assert client.post(f"{API}/workspaces", json={"title": "No auth"}).status_code == 401
    w = client.post(f"{API}/workspaces", headers=researcher, json={"title": "Isolation test", "research_question": "q?"}).json()
    it = client.post(f"{API}/workspaces/{w['id']}/items", headers=researcher, json={"item_type": "note", "note": "hello"})
    assert it.status_code == 201
    assert client.get(f"{API}/workspaces/{w['id']}", headers=analyst).status_code == 404  # not the owner
    assert client.post(f"{API}/workspaces/{w['id']}/items", headers=analyst, json={"item_type": "note"}).status_code == 404
    assert client.post(f"{API}/workspaces/{w['id']}/items", headers=researcher, json={"item_type": "bogus"}).status_code == 422
    got = client.get(f"{API}/workspaces/{w['id']}", headers=researcher).json()
    assert got["counts"] == {"note": 1} and got["items"][0]["note"] == "hello"
    assert client.delete(f"{API}/workspaces/{w['id']}/items/{it.json()['id']}", headers=researcher).status_code == 204


def test_save_is_idempotent_for_documents(client, researcher):
    w = client.post(f"{API}/workspaces", headers=researcher, json={"title": "Idem"}).json()
    body = {"item_type": "document", "ref_id": "doc-1", "title": "T"}
    a = client.post(f"{API}/workspaces/{w['id']}/items", headers=researcher, json=body).json()
    b = client.post(f"{API}/workspaces/{w['id']}/items", headers=researcher, json=body).json()
    assert a["id"] == b["id"]


def test_seeded_workspace_exports_brief_with_provenance(client, researcher):
    ws = client.get(f"{API}/workspaces", headers=researcher).json()
    seeded = next(w for w in ws if w["title"] == "Land-record digitization and disputes")
    brief = client.get(f"{API}/workspaces/{seeded['id']}/brief", headers=researcher).json()["content"]
    for needle in ("Cited findings", "Sources", "[DEMO]", "Scenarios", "input hash", "not a guaranteed outcome", "Generated:"):
        assert needle in brief


def test_audit_records_key_actions_without_raw_query(client, admin, researcher, db):
    marker = "distinctive audit query phrase about paddy terraces"
    client.post(f"{API}/search", headers=researcher, json={"query": marker})
    client.post(f"{API}/research/ask", headers=researcher, json={"question": marker + " please"})
    events = db.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(60)).all()
    actions = {e.action for e in events}
    assert {"SEARCH_EXECUTED", "AI_QUERY_EXECUTED"} <= actions
    assert all(marker not in str(e.meta) for e in events)  # data minimisation: hash only
    ev = next(e for e in events if e.action == "SEARCH_EXECUTED")
    assert ev.actor_role == "researcher" and ev.meta["query_sha"] and ev.ip and ev.actor_id


def test_audit_endpoint_admin_only_and_filterable(client, admin, researcher):
    r = client.get(f"{API}/admin/audit?action=USER_LOGIN&limit=5", headers=admin).json()
    assert r["total"] >= 1 and all(e["action"] == "USER_LOGIN" for e in r["events"])
    assert client.get(f"{API}/admin/audit", headers=researcher).status_code == 403


def test_restricted_document_state_and_denial_audited(client, analyst, db):
    hit = client.post(f"{API}/search", headers=analyst, json={"query": "pending mutation caseloads trained data-entry staff"}).json()["results"]
    rid = next(r["document_id"] for r in hit if r["access_level"] == "restricted")
    denied = client.get(f"{API}/documents/{rid}")
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "RESTRICTED_DOCUMENT"
    assert "restricted to authorized users" in denied.json()["error"]["message"]
    assert client.get(f"{API}/documents/{rid}", headers=analyst).status_code == 200
    assert db.scalar(select(AuditEvent).where(AuditEvent.action == "RESTRICTED_DOCUMENT_DENIED", AuditEvent.entity_id == rid))


def test_expert_can_annotate_researcher_cannot(client, expert, researcher):
    did = client.post(f"{API}/search", json={"query": "land record digitization"}).json()["results"][0]["document_id"]
    assert client.post(f"{API}/documents/{did}/annotations", headers=researcher, json={"text": "nope nope"}).status_code == 403
    r = client.post(f"{API}/documents/{did}/annotations", headers=expert, json={"text": "Method is descriptive only.", "kind": "flag"})
    assert r.status_code == 201
    assert client.get(f"{API}/documents/{did}/annotations", headers=expert).json()[-1]["kind"] == "flag"
