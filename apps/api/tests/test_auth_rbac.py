import jwt
import pytest

from tests.conftest import API


def test_health(client):
    r = client.get(f"{API}/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_security_headers(client):
    r = client.get(f"{API}/health")
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["x-frame-options"] == "DENY"


def test_login_bad_password_and_unknown_user(client):
    for email in ("researcher@demo.sih", "nobody@demo.sih"):
        r = client.post(f"{API}/auth/login", json={"email": email, "password": "wrong-password"})
        assert r.status_code == 401 and r.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_me_requires_auth_and_returns_role(client, researcher):
    assert client.get(f"{API}/auth/me").status_code == 401
    assert client.get(f"{API}/auth/me", headers=researcher).json()["role"] == "researcher"


def test_tampered_and_garbage_tokens_rejected(client, researcher):
    assert client.get(f"{API}/auth/me", headers={"Authorization": "Bearer abc.def.ghi"}).status_code == 401
    forged = jwt.encode({"sub": "00000000-0000-0000-0000-000000000000", "role": "admin"}, "wrong-secret-wrong-secret-wrong-secret", algorithm="HS256")
    assert client.get(f"{API}/admin/users", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_register_always_researcher(client):
    r = client.post(f"{API}/auth/register", json={"name": "New Person", "email": "new1@example.org", "password": "a-long-password-1", "role": "admin"})
    assert r.status_code == 201 and r.json()["user"]["role"] == "researcher"
    assert client.post(f"{API}/auth/register", json={"name": "Dup", "email": "new1@example.org", "password": "a-long-password-1"}).status_code == 409
    assert client.post(f"{API}/auth/register", json={"name": "Weak", "email": "weak@example.org", "password": "short"}).status_code == 422


# (method, path, body) -> which role fixtures may call it
MATRIX = [
    ("get", "/workspaces", None, {"researcher", "analyst", "expert", "admin"}),
    ("get", "/scenarios", None, {"researcher", "analyst", "expert", "admin"}),
    ("get", "/admin/users", None, {"admin"}),
    ("get", "/admin/audit", None, {"admin"}),
    ("get", "/admin/documents", None, {"expert", "admin"}),
    ("get", "/admin/models", None, {"expert", "admin"}),
]


@pytest.mark.parametrize("method,path,body,allowed", MATRIX)
def test_rbac_matrix(client, researcher, analyst, expert, admin, method, path, body, allowed):
    assert getattr(client, method)(f"{API}{path}").status_code == 401  # public
    for name, hdr in {"researcher": researcher, "analyst": analyst, "expert": expert, "admin": admin}.items():
        code = getattr(client, method)(f"{API}{path}", headers=hdr).status_code
        assert (code == 200) == (name in allowed), f"{name} -> {code} on {path}"
        if name not in allowed:
            assert code == 403


def test_public_can_read_public_content(client):
    assert client.get(f"{API}/dashboard").status_code == 200
    assert client.get(f"{API}/indicators").status_code == 200
    assert client.get(f"{API}/gis/layers/digitization_coverage").status_code == 200
    assert client.post(f"{API}/search", json={"query": "land record digitization"}).status_code == 200


def test_admin_cannot_change_own_role_and_role_change_is_audited(client, admin, db):
    from sqlalchemy import select
    from app.models import User, AuditEvent
    users = client.get(f"{API}/admin/users", headers=admin).json()
    me = next(u for u in users if u["email"] == "admin@demo.sih")
    assert client.patch(f"{API}/admin/users/{me['id']}/role", headers=admin, json={"role": "researcher"}).status_code == 409
    target = client.post(f"{API}/auth/register", json={"name": "Promo Tee", "email": "promo@example.org", "password": "a-long-password-1"}).json()["user"]
    r = client.patch(f"{API}/admin/users/{target['id']}/role", headers=admin, json={"role": "analyst"})
    assert r.status_code == 200
    assert db.scalar(select(AuditEvent).where(AuditEvent.action == "USER_ROLE_CHANGED", AuditEvent.entity_id == target["id"]))
    assert client.patch(f"{API}/admin/users/{target['id']}/role", headers=admin, json={"role": "superuser"}).status_code == 422
    # stale token keeps no privilege: role is re-read from DB
    old = client.post(f"{API}/auth/login", json={"email": "promo@example.org", "password": "a-long-password-1"}).json()["access_token"]
    assert client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {old}"}).json()["role"] == "analyst"


def test_rate_limit_triggers(client):
    from app.core import ratelimit
    from app.core.config import get_settings
    s = get_settings()
    s.rate_limit_enabled = True
    ratelimit.reset()
    try:
        codes = [client.post(f"{API}/auth/login", json={"email": "x@y.org", "password": "nope"}).status_code for _ in range(12)]
        assert 429 in codes
    finally:
        s.rate_limit_enabled = False
        ratelimit.reset()
