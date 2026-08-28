import os

# Only used as a fallback so importing database.py doesn't raise when no
# .env is present (e.g. CI): must stay a postgres-style URL, since
# database.py's own create_engine() call passes pool_size/max_overflow,
# which SQLite's pool implementation rejects. The real test database below
# is SQLite in-memory and is wired in via the get_db dependency override —
# this URL is never actually connected to.
os.environ.setdefault("DATABASE_URL", "postgresql://unused:unused@localhost/unused")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

import app as app_module
import pytest
from database import get_db
from fastapi.testclient import TestClient
from models import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# Never let the test suite touch DATABASE_URL's real target: override the
# get_db dependency everywhere it's used, and no-op init_db (the startup
# event would otherwise create tables against the real database).
app_module.app.dependency_overrides[get_db] = _override_get_db
app_module.init_db = lambda: None


@pytest.fixture
def _clean_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(_clean_database):
    with TestClient(app_module.app) as test_client:
        yield test_client


@pytest.fixture
def make_user(client):
    """Create a user via POST /users. Returns (username, password)."""

    def _make_user(username="testuser", password="testpassword123"):
        response = client.post("/users", json={"username": username, "password": password})
        assert response.status_code == 201, response.text
        return username, password

    return _make_user


@pytest.fixture
def auth_headers(client, make_user):
    """Create a user, log in, and return Authorization headers for them."""

    def _auth_headers(username="testuser", password="testpassword123"):
        make_user(username, password)
        response = client.post(
            "/auth/login",
            data={"username": username, "password": password},
        )
        assert response.status_code == 200, response.text
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _auth_headers
