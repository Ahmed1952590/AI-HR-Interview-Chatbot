"""Test setup: a temporary data folder and an offline hashing embedder (EMBED_MODEL=fake), so the tests need
no internet, no model download and never touch the real database.

Shared helpers/fixtures used by the test files: auth(), upload(), SAMPLE, client, admin, candidate, dataset.
"""
import os
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="hr_tests_")
os.environ["EMBED_MODEL"] = "fake"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["ADMIN_EMAIL"] = "admin@example.com"
os.environ["ADMIN_PASSWORD"] = "Admin123!"
sys.path.insert(0, str(BACKEND))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

SAMPLE = ROOT / "data" / "sample_dataset.csv"


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def upload(client, admin_headers, path):
    """POST a dataset file to /dataset/upload (background import runs before the call returns in TestClient)."""
    path = pathlib.Path(path)
    ctype = {".csv": "text/csv", ".json": "application/json"}.get(path.suffix.lower(), "text/plain")
    with open(path, "rb") as f:
        return client.post("/dataset/upload", headers=admin_headers, files={"file": (path.name, f, ctype)})


@pytest.fixture(scope="session")
def client():
    if not SAMPLE.exists():
        subprocess.check_call([sys.executable, str(BACKEND / "scripts" / "make_sample_dataset.py")])
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def admin(client):
    r = client.post("/login", json={"email": "admin@example.com", "password": "Admin123!"})
    assert r.status_code == 200, r.text
    return auth(r.json()["access_token"])


@pytest.fixture(scope="session")
def candidate(client):
    r = client.post("/register", json={"name": "Test Candidate", "email": "candidate@example.com", "password": "secret1"})
    assert r.status_code == 200, r.text
    return auth(r.json()["access_token"])


@pytest.fixture(scope="session")
def dataset(client, admin):
    """Imports the 96-question sample dataset once and returns GET /dataset/status."""
    r = upload(client, admin, SAMPLE)
    assert r.status_code == 200, r.text
    st = client.get("/dataset/status", headers=admin).json()
    assert st["datasets"][0]["status"] == "completed", st["datasets"][0]
    return st
