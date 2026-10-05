import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="sih26019-test-")
os.environ.update(DATABASE_URL=f"sqlite:///{_tmp}/test.sqlite3", OBJECT_STORAGE_URL=f"{_tmp}/store", ENVIRONMENT="test",
                  RATE_LIMIT_ENABLED="false", JWT_SECRET="test-secret-test-secret-test-secret-123", LLM_PROVIDER="extractive",
                  EMBEDDING_PROVIDER="hashing")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app.models  # noqa: E402,F401
from app.core.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seed.identity import DEMO_PASSWORD  # noqa: E402
from app.seed.run import seed_all  # noqa: E402

API = "/api/v1"
QUESTION = "What evidence exists on land-record digitization and land-dispute outcomes in India?"


@pytest.fixture(scope="session", autouse=True)
def _seeded():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_all(db)
    yield


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    with SessionLocal() as s:
        yield s


def _login(client, email):
    r = client.post(f"{API}/auth/login", json={"email": email, "password": DEMO_PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def researcher(client):
    return _login(client, "researcher@demo.sih")


@pytest.fixture(scope="session")
def analyst(client):
    return _login(client, "analyst@demo.sih")


@pytest.fixture(scope="session")
def expert(client):
    return _login(client, "expert@demo.sih")


@pytest.fixture(scope="session")
def admin(client):
    return _login(client, "admin@demo.sih")
