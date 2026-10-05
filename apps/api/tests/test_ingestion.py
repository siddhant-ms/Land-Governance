import io
import uuid

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from tests.conftest import API


def up(client, hdr, name, data, meta="{}", **extra):
    return client.post(f"{API}/admin/documents/ingest", headers=hdr, files={"file": (name, data, "application/octet-stream")},
                       data={"metadata": meta, **extra})


def make_pdf(pages):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for txt in pages:
        y = 800
        for line in txt.split("\n"):
            c.drawString(50, y, line)
            y -= 16
        c.showPage()
    c.save()
    return buf.getvalue()


def test_upload_requires_admin(client, researcher, analyst):
    assert up(client, {}, "a.md", b"# x\nhello world text here").status_code == 401
    assert up(client, researcher, "a.md", b"# x\nhello world text here").status_code == 403
    assert up(client, analyst, "a.md", b"# x\nhello world text here").status_code == 403


@pytest.mark.parametrize("name,data,code", [
    ("evil.exe", b"MZ....", 415), ("fake.pdf", b"not a pdf at all", 415), ("empty.md", b"", 422),
    ("bin.txt", b"abc\x00def" * 20, 415), ("latin.txt", "caf\xe9 ".encode("latin-1") * 20, 415),
])
def test_upload_validation(client, admin, name, data, code):
    assert up(client, admin, name, data).status_code == code


def test_size_limit(client, admin):
    from app.core.config import get_settings
    s = get_settings()
    old, s.max_upload_bytes = s.max_upload_bytes, 500
    try:
        assert up(client, admin, "big.md", b"word " * 400).status_code == 413
    finally:
        s.max_upload_bytes = old


def test_full_lifecycle_pending_then_searchable_after_approval(client, admin, expert, researcher):
    body = ("# Mangrove tenure\nZanzibar mangrove tenure arrangements are described in this ingestion lifecycle fixture for testing purposes.\n\n"
            "<!-- page: 2 -->\n## Findings\nMangrove tenure security improved after community registration of shoreline parcels in the fixture.\n")
    r = up(client, admin, "mangrove.md", body.encode(), '{"title":"Mangrove Lifecycle Fixture","topics":["Mangrove"],"organization":"Fixture Org","is_demo":true}')
    assert r.status_code == 202, r.text
    did, job = r.json()["document_id"], r.json()["job"]["id"]
    st = client.get(f"{API}/admin/ingestion/{job}", headers=admin).json()
    assert st["status"] == "done" and st["stats"]["chunks"] >= 2 and st["stats"]["pages"] == 2  # bg task ran
    q = {"query": "zanzibar mangrove tenure"}
    titles = [r["title"] for r in client.post(f"{API}/search", json=q).json()["results"]]
    assert "Mangrove Lifecycle Fixture" not in titles  # pending_review => not searchable
    assert client.get(f"{API}/documents/{did}").status_code == 404  # invisible to public
    assert client.post(f"{API}/admin/documents/{did}/approve", headers=researcher).status_code == 403
    assert client.post(f"{API}/admin/documents/{did}/approve", headers=expert).status_code == 200
    res = client.post(f"{API}/search", json=q).json()["results"]
    assert res and res[0]["title"] == "Mangrove Lifecycle Fixture"
    assert res[0]["passages"][0]["page"] in (1, 2)
    # duplicate content blocked
    assert up(client, admin, "again.md", body.encode()).status_code == 409


def test_pdf_ingestion_keeps_page_numbers(client, admin):
    pdf = make_pdf(["Alpha page one talks about quokka habitat registry procedures in detail. " * 1,
                    "Beta page two covers wombat cadastral survey reconciliation across many parcels. " * 1])
    r = up(client, admin, "pdf-fixture.pdf", pdf, '{"title":"PDF Fixture","is_demo":true}', )
    assert r.status_code == 202
    job = client.get(f"{API}/admin/ingestion/{r.json()['job']['id']}", headers=admin).json()
    assert job["status"] == "done" and job["stats"]["pages"] == 2
    did = r.json()["document_id"]
    client.post(f"{API}/admin/documents/{did}/approve", headers=admin)
    doc = client.get(f"{API}/documents/{did}").json()
    pages = {c["page"] for c in doc["chunks"]}
    assert pages == {1, 2}
    assert doc["version"]["content_hash"] and len(doc["version"]["content_hash"]) == 64


def test_new_version_keeps_history(client, admin, db):
    from sqlalchemy import select
    from app.models import DocumentVersion
    r = up(client, admin, "v1.md", b"# Doc\nVersioned fixture paragraph about wetland registry alpha version one content here.", '{"title":"Versioned Fixture"}')
    did = r.json()["document_id"]
    r2 = up(client, admin, "v2.md", b"# Doc\nVersioned fixture paragraph about wetland registry beta version two content here.", "{}", document_id=did)
    assert r2.status_code == 202
    vers = db.scalars(select(DocumentVersion).where(DocumentVersion.document_id == uuid.UUID(did)).order_by(DocumentVersion.version_no)).all()
    assert [v.version_no for v in vers] == [1, 2] and vers[1].parent_version_id == vers[0].id
    assert [v.is_current for v in vers] == [False, True]


def test_ssrf_guard_blocks_internal_urls():
    from app.core.errors import AppError
    from app.services.ingestion.urlfetch import assert_public_url
    for u in ("http://127.0.0.1/x", "http://localhost:8000", "http://169.254.169.254/latest/meta-data", "file:///etc/passwd", "ftp://a.b/c"):
        with pytest.raises(AppError):
            assert_public_url(u)


def test_chunker_and_extraction_units():
    from app.services.ingestion.chunking import chunk_pages
    text = "# A\n" + ("word " * 300) + "\n\n## B\n" + ("term " * 60)
    chunks = chunk_pages([(3, text)])
    assert all(c.page_no == 3 for c in chunks) and {c.section for c in chunks} == {"A", "B"}
    assert max(len(c.text.split()) for c in chunks) <= 240
