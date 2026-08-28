"""Characterization tests for REQ-AUTH-1..5 (see BUSINESS.md).

The authentication behavior these pin down is already implemented in
``auth.py`` and wired into ``app.py``; these tests exist to lock it in.
"""

import time
from datetime import timedelta

import auth
import pytest
from conftest import TestingSessionLocal
from jose import jwt
from models import UserModel

PROTECTED_URL = "/users/testuser/full"


# ==================== REQ-AUTH-1 ====================


def test_login_with_valid_credentials_returns_bearer_token(client, make_user):
    """REQ-AUTH-1: correct credentials yield 200 + access_token/token_type."""
    username, password = make_user()

    response = client.post("/auth/login", data={"username": username, "password": password})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str)
    assert body["access_token"]


def test_login_token_identifies_the_authenticated_user(client, make_user):
    """REQ-AUTH-1: the issued token names the user who authenticated."""
    username, password = make_user()

    response = client.post("/auth/login", data={"username": username, "password": password})

    token_data = auth.decode_access_token(response.json()["access_token"])
    assert token_data is not None
    assert token_data.username == username


# ==================== REQ-AUTH-2 ====================


def test_login_with_unknown_username_returns_401(client, make_user):
    """REQ-AUTH-2: a username that does not exist is rejected with 401."""
    make_user()

    response = client.post(
        "/auth/login", data={"username": "nosuchuser", "password": "testpassword123"}
    )

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_login_with_wrong_password_returns_401(client, make_user):
    """REQ-AUTH-2: an existing user with the wrong password gets 401."""
    username, _ = make_user()

    response = client.post(
        "/auth/login", data={"username": username, "password": "wrongpassword123"}
    )

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_failed_login_returns_no_access_token(client, make_user):
    """REQ-AUTH-2: a rejected login body carries no token."""
    username, _ = make_user()

    response = client.post(
        "/auth/login", data={"username": username, "password": "wrongpassword123"}
    )

    assert "access_token" not in response.json()


# ==================== REQ-AUTH-3 ====================


def test_issued_token_expires_thirty_minutes_after_issuance(client, make_user):
    """REQ-AUTH-3: the token's exp claim is issuance + 30 minutes."""
    username, password = make_user()

    before = time.time()
    response = client.post("/auth/login", data={"username": username, "password": password})
    after = time.time()

    payload = jwt.decode(
        response.json()["access_token"], auth.SECRET_KEY, algorithms=[auth.ALGORITHM]
    )
    expected_seconds = auth.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    assert auth.ACCESS_TOKEN_EXPIRE_MINUTES == 30
    assert before + expected_seconds - 5 <= payload["exp"] <= after + expected_seconds + 5


def test_decode_access_token_rejects_an_expired_token():
    """REQ-AUTH-3: an expired token no longer decodes to a TokenData."""
    expired_token = auth.create_access_token(
        data={"sub": "testuser"}, expires_delta=timedelta(minutes=-1)
    )

    assert auth.decode_access_token(expired_token) is None


def test_protected_endpoint_rejects_an_expired_token(client, make_user):
    """REQ-AUTH-3: a protected endpoint answers 401 for an expired token."""
    username, _ = make_user()
    expired_token = auth.create_access_token(
        data={"sub": username}, expires_delta=timedelta(minutes=-1)
    )

    response = client.get(PROTECTED_URL, headers={"Authorization": f"Bearer {expired_token}"})

    assert response.status_code == 401


# ==================== REQ-AUTH-4 ====================


def test_created_user_password_is_stored_as_a_bcrypt_hash(client, make_user):
    """REQ-AUTH-4: the persisted password is a bcrypt hash."""
    username, _ = make_user()

    db = TestingSessionLocal()
    try:
        stored = db.query(UserModel).filter(UserModel.username == username).first()
        hashed = stored.hashed_password
    finally:
        db.close()

    assert hashed.startswith("$2b$")
    assert auth.verify_password("testpassword123", hashed)


def test_created_user_plaintext_password_is_never_persisted(client, make_user):
    """REQ-AUTH-4: the plaintext password appears nowhere on the user row."""
    username, password = make_user()

    db = TestingSessionLocal()
    try:
        stored = db.query(UserModel).filter(UserModel.username == username).first()
        persisted_values = [getattr(stored, column.name) for column in UserModel.__table__.columns]
    finally:
        db.close()

    assert password not in persisted_values
    assert all(password not in value for value in persisted_values if isinstance(value, str))


def test_user_creation_response_omits_the_password(client):
    """REQ-AUTH-4: POST /users never echoes the password back."""
    response = client.post("/users", json={"username": "hashuser", "password": "testpassword123"})

    assert response.status_code == 201, response.text
    body = response.json()
    assert "password" not in body
    assert "hashed_password" not in body


# ==================== REQ-AUTH-5 ====================


def test_protected_endpoint_without_authorization_header_returns_401(client, make_user):
    """REQ-AUTH-5: a missing Authorization header is rejected with 401."""
    make_user()

    response = client.get(PROTECTED_URL)

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "header_value",
    ["testtoken", "Basic dXNlcjpwYXNz", "Bearer"],
    ids=["no-scheme", "wrong-scheme", "scheme-without-token"],
)
def test_protected_endpoint_with_malformed_authorization_header_returns_401(
    client, make_user, header_value
):
    """REQ-AUTH-5: a malformed Authorization header is rejected with 401."""
    make_user()

    response = client.get(PROTECTED_URL, headers={"Authorization": header_value})

    assert response.status_code == 401


def test_protected_endpoint_with_invalid_token_returns_401(client, make_user):
    """REQ-AUTH-5: a garbage bearer token is rejected with 401."""
    make_user()

    response = client.get(PROTECTED_URL, headers={"Authorization": "Bearer not-a-real-jwt"})

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_protected_endpoint_with_token_for_deleted_user_returns_401(client, make_user):
    """REQ-AUTH-5: a well-formed token whose subject no longer exists is 401."""
    make_user()
    orphan_token = auth.create_access_token(data={"sub": "ghostuser"})

    response = client.get(PROTECTED_URL, headers={"Authorization": f"Bearer {orphan_token}"})

    assert response.status_code == 401
