import os
import sys
import tempfile
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure backend package root is on path
BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

# Use an isolated SQLite DB for tests before app imports engine
TEST_DB = Path(tempfile.gettempdir()) / f"docuguard-test-{uuid.uuid4().hex}.db"

os.environ["ENVIRONMENT"] = "development"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-not-for-production-use-only"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["AUTH_RATE_LIMIT_PER_MINUTE"] = "1000"
os.environ["UPLOAD_RATE_LIMIT_PER_MINUTE"] = "1000"
os.environ["CORS_ORIGINS"] = "http://127.0.0.1:5173"

from app.database import Base, engine, init_db  # noqa: E402
from app.main import app  # noqa: E402


def pytest_sessionfinish(session, exitstatus):
    engine.dispose()
    TEST_DB.unlink(missing_ok=True)


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    init_db()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers(client):
    res = client.post(
        "/api/auth/register",
        json={
            "email": "alice@example.com",
            "full_name": "Alice Example",
            "password": "securepass1",
            "confirm_password": "securepass1",
        },
    )
    assert res.status_code == 201, res.text
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def second_user_headers(client):
    res = client.post(
        "/api/auth/register",
        json={
            "email": "bob@example.com",
            "full_name": "Bob Example",
            "password": "securepass1",
            "confirm_password": "securepass1",
        },
    )
    assert res.status_code == 201, res.text
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
