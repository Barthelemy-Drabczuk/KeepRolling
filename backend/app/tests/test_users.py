"""Characterization tests for REQ-USER-1..5 (see BUSINESS.md).

The behavior these pin down is already implemented by the user endpoints
in ``app.py``.
"""

import pytest
from conftest import TestingSessionLocal
from models import EntryModel, MoodModel, UserModel


def _fetch_user(username):
    """Read a user row straight from the database, bypassing the API."""
    db = TestingSessionLocal()
    try:
        return db.query(UserModel).filter(UserModel.username == username).first()
    finally:
        db.close()


def _count_rows(model, user_id):
    db = TestingSessionLocal()
    try:
        return db.query(model).filter(model.user_id == user_id).count()
    finally:
        db.close()


# ==================== REQ-USER-1 ====================


def test_create_user_returns_201_with_public_profile_fields(client):
    """REQ-USER-1: POST /users answers 201 with id, username and created_at."""
    response = client.post("/users", json={"username": "newuser", "password": "testpassword123"})

    assert response.status_code == 201, response.text
    body = response.json()
    assert isinstance(body["id"], int)
    assert body["username"] == "newuser"
    assert body["created_at"]


def test_create_user_response_carries_no_password_field(client):
    """REQ-USER-1: the creation response exposes no password of any kind."""
    response = client.post("/users", json={"username": "newuser", "password": "testpassword123"})

    body = response.json()
    assert "password" not in body
    assert "hashed_password" not in body


@pytest.mark.parametrize("length", [3, 50], ids=["min-length", "max-length"])
def test_create_user_accepts_usernames_at_the_length_bounds(client, length):
    """REQ-USER-1: usernames of exactly 3 and exactly 50 characters are accepted."""
    username = "u" * length

    response = client.post("/users", json={"username": username, "password": "testpassword123"})

    assert response.status_code == 201, response.text
    assert response.json()["username"] == username


@pytest.mark.parametrize("length", [2, 51], ids=["too-short", "too-long"])
def test_create_user_rejects_usernames_outside_the_length_bounds(client, length):
    """REQ-USER-1: usernames shorter than 3 or longer than 50 are rejected."""
    response = client.post("/users", json={"username": "u" * length, "password": "testpassword123"})

    assert response.status_code == 422


def test_create_user_accepts_a_password_of_exactly_eight_characters(client):
    """REQ-USER-1: the 8-character password minimum is inclusive."""
    response = client.post("/users", json={"username": "shortpw", "password": "12345678"})

    assert response.status_code == 201, response.text


def test_create_user_rejects_a_password_shorter_than_eight_characters(client):
    """REQ-USER-1: a 7-character password does not create an account."""
    response = client.post("/users", json={"username": "shortpw", "password": "1234567"})

    assert response.status_code == 422
    assert _fetch_user("shortpw") is None


# ==================== REQ-USER-2 ====================


def test_create_user_with_an_already_registered_username_returns_400(client, make_user):
    """REQ-USER-2: a duplicate username is rejected with 400."""
    username, _ = make_user("takenuser")

    response = client.post("/users", json={"username": username, "password": "otherpassword123"})

    assert response.status_code == 400


def test_duplicate_username_does_not_create_a_second_account(client, make_user):
    """REQ-USER-2: the rejected duplicate leaves exactly one stored account."""
    username, _ = make_user("takenuser")

    client.post("/users", json={"username": username, "password": "otherpassword123"})

    db = TestingSessionLocal()
    try:
        assert db.query(UserModel).filter(UserModel.username == username).count() == 1
    finally:
        db.close()


# ==================== REQ-USER-3 ====================


def test_update_own_password_returns_200_with_the_profile(client, auth_headers):
    """REQ-USER-3: a caller updating their own password gets 200 + their profile."""
    headers = auth_headers("alice")

    response = client.put("/users/alice", json={"password": "brandnewpassword"}, headers=headers)

    assert response.status_code == 200, response.text
    assert response.json()["username"] == "alice"


def test_updated_password_authenticates_on_a_subsequent_login(client, auth_headers):
    """REQ-USER-3: the new password is what a later login must use."""
    headers = auth_headers("alice")
    client.put("/users/alice", json={"password": "brandnewpassword"}, headers=headers)

    response = client.post(
        "/auth/login", data={"username": "alice", "password": "brandnewpassword"}
    )

    assert response.status_code == 200, response.text


def test_old_password_stops_authenticating_after_an_update(client, auth_headers):
    """REQ-USER-3: the replaced password no longer authenticates."""
    headers = auth_headers("alice", "originalpassword")
    client.put("/users/alice", json={"password": "brandnewpassword"}, headers=headers)

    response = client.post(
        "/auth/login", data={"username": "alice", "password": "originalpassword"}
    )

    assert response.status_code == 401


def test_update_another_users_password_returns_403(client, auth_headers, make_user):
    """REQ-USER-3: updating a username other than the caller's is forbidden."""
    headers = auth_headers("alice")
    make_user("bob", "bobspassword123")

    response = client.put("/users/bob", json={"password": "hijackedpassword"}, headers=headers)

    assert response.status_code == 403


def test_forbidden_update_leaves_the_other_users_password_unchanged(
    client, auth_headers, make_user
):
    """REQ-USER-3: a 403'd update does not alter the target user's password."""
    headers = auth_headers("alice")
    make_user("bob", "bobspassword123")

    client.put("/users/bob", json={"password": "hijackedpassword"}, headers=headers)

    response = client.post("/auth/login", data={"username": "bob", "password": "bobspassword123"})
    assert response.status_code == 200, response.text


# ==================== REQ-USER-4 ====================


def test_delete_own_account_returns_204(client, auth_headers):
    """REQ-USER-4: deleting one's own account answers 204."""
    headers = auth_headers("alice")

    response = client.delete("/users/alice", headers=headers)

    assert response.status_code == 204


def test_deleted_account_is_removed_from_storage(client, auth_headers):
    """REQ-USER-4: the deleted user's row is gone."""
    headers = auth_headers("alice")

    client.delete("/users/alice", headers=headers)

    assert _fetch_user("alice") is None


def test_deleting_a_user_cascade_deletes_their_moods(client, auth_headers):
    """REQ-USER-4: the deleted user's moods are removed with the account."""
    headers = auth_headers("alice")
    user_id = _fetch_user("alice").id
    created = client.post(
        "/users/alice/moods", json={"energy": 0.5, "valence": 0.5}, headers=headers
    )
    assert created.status_code == 201, created.text
    assert _count_rows(MoodModel, user_id) == 1

    client.delete("/users/alice", headers=headers)

    assert _count_rows(MoodModel, user_id) == 0


def test_deleting_a_user_cascade_deletes_their_entries(client, auth_headers):
    """REQ-USER-4: the deleted user's journal entries are removed too."""
    headers = auth_headers("alice")
    user_id = _fetch_user("alice").id
    created = client.post(
        "/users/alice/entries", json={"content": "a journal entry"}, headers=headers
    )
    assert created.status_code == 201, created.text
    assert _count_rows(EntryModel, user_id) == 1

    client.delete("/users/alice", headers=headers)

    assert _count_rows(EntryModel, user_id) == 0


def test_delete_another_users_account_returns_403(client, auth_headers, make_user):
    """REQ-USER-4: deleting a username other than the caller's is forbidden."""
    headers = auth_headers("alice")
    make_user("bob", "bobspassword123")

    response = client.delete("/users/bob", headers=headers)

    assert response.status_code == 403


def test_forbidden_delete_leaves_the_other_users_account_intact(client, auth_headers, make_user):
    """REQ-USER-4: a 403'd delete does not remove the target user."""
    headers = auth_headers("alice")
    make_user("bob", "bobspassword123")

    client.delete("/users/bob", headers=headers)

    assert _fetch_user("bob") is not None


# ==================== REQ-USER-5 ====================


def test_full_view_returns_the_callers_profile_fields(client, auth_headers):
    """REQ-USER-5: /full carries the target user's profile fields."""
    headers = auth_headers("alice")

    response = client.get("/users/alice/full", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["username"] == "alice"
    assert isinstance(body["id"], int)
    assert body["created_at"]


def test_full_view_includes_all_of_the_callers_moods(client, auth_headers):
    """REQ-USER-5: /full lists the user's moods."""
    headers = auth_headers("alice")
    client.post("/users/alice/moods", json={"energy": 0.5, "valence": -0.25}, headers=headers)
    client.post("/users/alice/moods", json={"energy": -0.75, "valence": 0.1}, headers=headers)

    response = client.get("/users/alice/full", headers=headers)

    moods = response.json()["moods"]
    assert len(moods) == 2
    assert {(m["energy"], m["valence"]) for m in moods} == {(0.5, -0.25), (-0.75, 0.1)}


def test_full_view_includes_all_of_the_callers_entries(client, auth_headers):
    """REQ-USER-5: /full lists the user's journal entries."""
    headers = auth_headers("alice")
    client.post("/users/alice/entries", json={"content": "first entry"}, headers=headers)
    client.post("/users/alice/entries", json={"content": "second entry"}, headers=headers)

    response = client.get("/users/alice/full", headers=headers)

    entries = response.json()["entries"]
    assert {entry["content"] for entry in entries} == {"first entry", "second entry"}


def test_full_view_of_another_user_returns_403(client, auth_headers, make_user):
    """REQ-USER-5: /full is self-only — another username is forbidden."""
    headers = auth_headers("alice")
    make_user("bob", "bobspassword123")

    response = client.get("/users/bob/full", headers=headers)

    assert response.status_code == 403
