"""Tests for REQ-ENTRY-1..4 (see BUSINESS.md).

All of these are characterization tests: the behavior they pin down is
already implemented by the journal-entry endpoints in ``app.py``, so they are
expected to pass as written. REQ-ENTRY-5 (the optional ``mood_id`` link) and
REQ-ENTRY-6 (unlinking on mood deletion) are marked "not yet implemented" in
BUSINESS.md and are deliberately *not* covered here — they are separate
follow-up work.

A note on REQ-ENTRY-4's "for that user" clause, mirroring the same
distinction already pinned in ``test_moods.py``. Every entry route authorizes
before it looks anything up, so the status code depends on which username
sits in the path:

* ``GET /users/bob/entries/{alice_entry_id}`` (caller bob, own username in
  the path, someone else's entry id) is the case REQ-ENTRY-4 describes ->
  404, because no entry with that id exists *for bob*.
* ``GET /users/alice/entries/{alice_entry_id}`` (caller bob, alice's username
  in the path) never reaches the entry lookup at all -> 403, from the same
  self-only rule REQ-ENTRY-1/REQ-ENTRY-3 state for the collection routes.

Both are covered below so the distinction stays pinned.
"""

from datetime import UTC, datetime, timedelta

import pytest
from conftest import TestingSessionLocal
from models import EntryModel, UserModel


def _fetch_user(username):
    """Read a user row straight from the database, bypassing the API."""
    db = TestingSessionLocal()
    try:
        return db.query(UserModel).filter(UserModel.username == username).first()
    finally:
        db.close()


def _fetch_entry(entry_id):
    """Read an entry row straight from the database, bypassing the API."""
    db = TestingSessionLocal()
    try:
        return db.query(EntryModel).filter(EntryModel.id == entry_id).first()
    finally:
        db.close()


def _count_entries(username):
    user = _fetch_user(username)
    db = TestingSessionLocal()
    try:
        return db.query(EntryModel).filter(EntryModel.user_id == user.id).count()
    finally:
        db.close()


def _create_entry(client, headers, username, content="A day like any other.", timestamp=None):
    """POST an entry and return the created body, asserting it succeeded."""
    payload = {"content": content}
    if timestamp is not None:
        payload["timestamp"] = timestamp
    response = client.post(f"/users/{username}/entries", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


# ==================== REQ-ENTRY-1 ====================


def test_create_entry_returns_201_with_the_stored_entry(client, auth_headers):
    """REQ-ENTRY-1: POST /users/{username}/entries answers 201 with the new entry."""
    headers = auth_headers("alice")

    response = client.post(
        "/users/alice/entries", json={"content": "Rained all afternoon."}, headers=headers
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["content"] == "Rained all afternoon."
    assert isinstance(body["id"], int)


def test_created_entry_is_owned_by_the_authenticated_caller(client, auth_headers):
    """REQ-ENTRY-1: the created entry is attached to the calling user's id."""
    headers = auth_headers("alice")

    body = _create_entry(client, headers, "alice")

    assert body["user_id"] == _fetch_user("alice").id


def test_created_entry_content_is_persisted(client, auth_headers):
    """REQ-ENTRY-1: the content supplied on create lands in the database row."""
    headers = auth_headers("alice")

    body = _create_entry(client, headers, "alice", content="Walked by the river.")

    assert _fetch_entry(body["id"]).content == "Walked by the river."


def test_create_entry_for_another_username_returns_403(client, auth_headers, make_user):
    """REQ-ENTRY-1: creating an entry under someone else's username is forbidden."""
    headers = auth_headers("alice")
    make_user("bob", "bobspassword123")

    response = client.post(
        "/users/bob/entries", json={"content": "Not mine to write."}, headers=headers
    )

    assert response.status_code == 403


def test_forbidden_create_stores_no_entry_for_the_other_user(client, auth_headers, make_user):
    """REQ-ENTRY-1: a 403'd create leaves the target user with no entries."""
    headers = auth_headers("alice")
    make_user("bob", "bobspassword123")

    client.post("/users/bob/entries", json={"content": "Not mine to write."}, headers=headers)

    assert _count_entries("bob") == 0


def test_create_entry_requires_content(client, auth_headers):
    """REQ-ENTRY-1: content is a required field."""
    headers = auth_headers("alice")

    response = client.post("/users/alice/entries", json={}, headers=headers)

    assert response.status_code == 422


def test_create_entry_accepts_content_of_exactly_1_character(client, auth_headers):
    """REQ-ENTRY-1: the 1-5000 character range is closed at its lower end."""
    headers = auth_headers("alice")

    response = client.post("/users/alice/entries", json={"content": "x"}, headers=headers)

    assert response.status_code == 201, response.text
    assert response.json()["content"] == "x"


def test_create_entry_accepts_content_of_exactly_5000_characters(client, auth_headers):
    """REQ-ENTRY-1: the 1-5000 character range is closed at its upper end."""
    headers = auth_headers("alice")
    content = "c" * 5000

    response = client.post("/users/alice/entries", json={"content": content}, headers=headers)

    assert response.status_code == 201, response.text
    assert response.json()["content"] == content


def test_create_entry_rejects_empty_content(client, auth_headers):
    """REQ-ENTRY-1: an empty string is below the 1-character minimum -> 422."""
    headers = auth_headers("alice")

    response = client.post("/users/alice/entries", json={"content": ""}, headers=headers)

    assert response.status_code == 422


def test_create_entry_rejects_content_longer_than_5000_characters(client, auth_headers):
    """REQ-ENTRY-1: 5001 characters is over the bound and is rejected with 422."""
    headers = auth_headers("alice")

    response = client.post("/users/alice/entries", json={"content": "c" * 5001}, headers=headers)

    assert response.status_code == 422


@pytest.mark.parametrize("content", ["", "c" * 5001], ids=["empty-content", "over-length-content"])
def test_rejected_out_of_range_entry_is_not_persisted(client, auth_headers, content):
    """REQ-ENTRY-1: a 422'd create writes no entry row."""
    headers = auth_headers("alice")

    client.post("/users/alice/entries", json={"content": content}, headers=headers)

    assert _count_entries("alice") == 0


# ==================== REQ-ENTRY-2 ====================


def test_created_entry_timestamp_defaults_to_now_in_utc(client, auth_headers):
    """REQ-ENTRY-2: an omitted timestamp defaults to the current UTC time."""
    headers = auth_headers("alice")
    # app.py stores a naive datetime.utcnow(); compare on the same naive-UTC
    # footing without re-introducing the deprecated call here.
    before = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1)

    body = _create_entry(client, headers, "alice")

    after = datetime.now(UTC).replace(tzinfo=None) + timedelta(seconds=1)
    assert before <= datetime.fromisoformat(body["timestamp"]) <= after


def test_supplied_timestamp_is_returned_unchanged(client, auth_headers):
    """REQ-ENTRY-2: an explicitly supplied timestamp is honored, not overwritten."""
    headers = auth_headers("alice")

    body = _create_entry(client, headers, "alice", timestamp="2020-01-02T03:04:05")

    assert datetime.fromisoformat(body["timestamp"]) == datetime(2020, 1, 2, 3, 4, 5)


def test_supplied_timestamp_is_persisted_as_given(client, auth_headers):
    """REQ-ENTRY-2: the supplied timestamp is what lands in the database."""
    headers = auth_headers("alice")

    body = _create_entry(client, headers, "alice", timestamp="2020-01-02T03:04:05")

    assert _fetch_entry(body["id"]).timestamp == datetime(2020, 1, 2, 3, 4, 5)


# ==================== REQ-ENTRY-3 ====================


def test_list_entries_returns_the_callers_own_entries(client, auth_headers):
    """REQ-ENTRY-3: GET /users/{username}/entries lists that caller's entries."""
    headers = auth_headers("alice")
    _create_entry(client, headers, "alice", content="First.")
    _create_entry(client, headers, "alice", content="Second.")

    response = client.get("/users/alice/entries", headers=headers)

    assert response.status_code == 200, response.text
    assert {e["content"] for e in response.json()} == {"First.", "Second."}


def test_list_entries_excludes_other_users_entries(client, auth_headers):
    """REQ-ENTRY-3: another user's entries never appear in the caller's list."""
    alice_headers = auth_headers("alice")
    bob_headers = auth_headers("bob", "bobspassword123")
    _create_entry(client, bob_headers, "bob", content="Bob's private thoughts.")
    _create_entry(client, alice_headers, "alice", content="Alice's own.")

    response = client.get("/users/alice/entries", headers=alice_headers)

    assert [e["content"] for e in response.json()] == ["Alice's own."]


def test_list_entries_for_another_username_returns_403(client, auth_headers, make_user):
    """REQ-ENTRY-3: listing another user's entries is forbidden."""
    headers = auth_headers("alice")
    make_user("bob", "bobspassword123")

    response = client.get("/users/bob/entries", headers=headers)

    assert response.status_code == 403


def test_list_entries_is_ordered_newest_first(client, auth_headers):
    """REQ-ENTRY-3: entries come back in descending timestamp order."""
    headers = auth_headers("alice")
    _create_entry(client, headers, "alice", timestamp="2024-01-01T00:00:00")
    _create_entry(client, headers, "alice", timestamp="2024-03-01T00:00:00")
    _create_entry(client, headers, "alice", timestamp="2024-02-01T00:00:00")

    response = client.get("/users/alice/entries", headers=headers)

    assert [e["timestamp"] for e in response.json()] == [
        "2024-03-01T00:00:00",
        "2024-02-01T00:00:00",
        "2024-01-01T00:00:00",
    ]


def test_list_entries_limit_caps_the_number_returned(client, auth_headers):
    """REQ-ENTRY-3: limit returns only that many entries, newest first."""
    headers = auth_headers("alice")
    for day in range(1, 6):
        _create_entry(client, headers, "alice", timestamp=f"2024-01-0{day}T00:00:00")

    response = client.get("/users/alice/entries?limit=2", headers=headers)

    assert [e["timestamp"] for e in response.json()] == [
        "2024-01-05T00:00:00",
        "2024-01-04T00:00:00",
    ]


def test_list_entries_skip_offsets_into_the_newest_first_order(client, auth_headers):
    """REQ-ENTRY-3: skip drops that many of the newest entries before limiting."""
    headers = auth_headers("alice")
    for day in range(1, 6):
        _create_entry(client, headers, "alice", timestamp=f"2024-01-0{day}T00:00:00")

    response = client.get("/users/alice/entries?skip=2&limit=2", headers=headers)

    assert [e["timestamp"] for e in response.json()] == [
        "2024-01-03T00:00:00",
        "2024-01-02T00:00:00",
    ]


def test_list_entries_skip_past_the_end_returns_an_empty_list(client, auth_headers):
    """REQ-ENTRY-3: skipping beyond the last entry yields no results."""
    headers = auth_headers("alice")
    _create_entry(client, headers, "alice")

    response = client.get("/users/alice/entries?skip=5", headers=headers)

    assert response.status_code == 200, response.text
    assert response.json() == []


def test_list_entries_without_pagination_params_returns_every_entry(client, auth_headers):
    """REQ-ENTRY-3: with no skip/limit given, a small set comes back in full."""
    headers = auth_headers("alice")
    for day in range(1, 6):
        _create_entry(client, headers, "alice", timestamp=f"2024-01-0{day}T00:00:00")

    response = client.get("/users/alice/entries", headers=headers)

    assert len(response.json()) == 5


# ==================== REQ-ENTRY-4 ====================


def test_get_unknown_entry_id_returns_404(client, auth_headers):
    """REQ-ENTRY-4: GET on an entry id that exists for nobody answers 404."""
    headers = auth_headers("alice")

    response = client.get("/users/alice/entries/9999", headers=headers)

    assert response.status_code == 404


def test_update_unknown_entry_id_returns_404(client, auth_headers):
    """REQ-ENTRY-4: PUT on an entry id that exists for nobody answers 404."""
    headers = auth_headers("alice")

    response = client.put(
        "/users/alice/entries/9999", json={"content": "Rewritten."}, headers=headers
    )

    assert response.status_code == 404


def test_delete_unknown_entry_id_returns_404(client, auth_headers):
    """REQ-ENTRY-4: DELETE on an entry id that exists for nobody answers 404."""
    headers = auth_headers("alice")

    response = client.delete("/users/alice/entries/9999", headers=headers)

    assert response.status_code == 404


def test_get_another_users_entry_id_under_own_username_returns_404(client, auth_headers):
    """REQ-ENTRY-4: an entry id owned by someone else does not exist for the caller."""
    alice_headers = auth_headers("alice")
    bob_headers = auth_headers("bob", "bobspassword123")
    alice_entry = _create_entry(client, alice_headers, "alice")

    response = client.get(f"/users/bob/entries/{alice_entry['id']}", headers=bob_headers)

    assert response.status_code == 404


def test_update_another_users_entry_id_under_own_username_returns_404(client, auth_headers):
    """REQ-ENTRY-4: PUT cannot reach an entry id owned by another user."""
    alice_headers = auth_headers("alice")
    bob_headers = auth_headers("bob", "bobspassword123")
    alice_entry = _create_entry(client, alice_headers, "alice")

    response = client.put(
        f"/users/bob/entries/{alice_entry['id']}",
        json={"content": "Bob was here."},
        headers=bob_headers,
    )

    assert response.status_code == 404


def test_failed_cross_user_update_leaves_the_entry_unchanged(client, auth_headers):
    """REQ-ENTRY-4: the 404'd update does not mutate the owner's entry."""
    alice_headers = auth_headers("alice")
    bob_headers = auth_headers("bob", "bobspassword123")
    alice_entry = _create_entry(client, alice_headers, "alice", content="Alice's words.")

    client.put(
        f"/users/bob/entries/{alice_entry['id']}",
        json={"content": "Bob was here."},
        headers=bob_headers,
    )

    assert _fetch_entry(alice_entry["id"]).content == "Alice's words."


def test_delete_another_users_entry_id_under_own_username_returns_404(client, auth_headers):
    """REQ-ENTRY-4: DELETE cannot reach an entry id owned by another user."""
    alice_headers = auth_headers("alice")
    bob_headers = auth_headers("bob", "bobspassword123")
    alice_entry = _create_entry(client, alice_headers, "alice")

    response = client.delete(f"/users/bob/entries/{alice_entry['id']}", headers=bob_headers)

    assert response.status_code == 404


def test_failed_cross_user_delete_leaves_the_entry_in_place(client, auth_headers):
    """REQ-ENTRY-4: the 404'd delete does not remove the owner's entry."""
    alice_headers = auth_headers("alice")
    bob_headers = auth_headers("bob", "bobspassword123")
    alice_entry = _create_entry(client, alice_headers, "alice")

    client.delete(f"/users/bob/entries/{alice_entry['id']}", headers=bob_headers)

    assert _fetch_entry(alice_entry["id"]) is not None


@pytest.mark.parametrize("method", ["get", "put", "delete"])
def test_reaching_an_entry_through_another_users_path_returns_403(client, auth_headers, method):
    """REQ-ENTRY-4 boundary: the owner's username in the path is refused before
    the entry lookup, so it is 403 rather than the 404 above."""
    alice_headers = auth_headers("alice")
    bob_headers = auth_headers("bob", "bobspassword123")
    alice_entry = _create_entry(client, alice_headers, "alice")
    url = f"/users/alice/entries/{alice_entry['id']}"

    if method == "put":
        response = client.put(url, json={"content": "Bob was here."}, headers=bob_headers)
    else:
        response = getattr(client, method)(url, headers=bob_headers)

    assert response.status_code == 403


def test_owner_can_still_get_their_own_entry_by_id(client, auth_headers):
    """REQ-ENTRY-4: the 404 rule is scoped — the real owner reads their entry fine."""
    headers = auth_headers("alice")
    created = _create_entry(client, headers, "alice", content="Mine to read.")

    response = client.get(f"/users/alice/entries/{created['id']}", headers=headers)

    assert response.status_code == 200, response.text
    assert response.json()["id"] == created["id"]


def test_owner_can_update_their_own_entry(client, auth_headers):
    """REQ-ENTRY-4: the 404 rule is scoped — the real owner's PUT succeeds."""
    headers = auth_headers("alice")
    created = _create_entry(client, headers, "alice", content="First draft.")

    response = client.put(
        f"/users/alice/entries/{created['id']}",
        json={"content": "Second draft."},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["content"] == "Second draft."


def test_owner_can_delete_their_own_entry(client, auth_headers):
    """REQ-ENTRY-4: the 404 rule is scoped — the real owner's DELETE removes the row."""
    headers = auth_headers("alice")
    created = _create_entry(client, headers, "alice")

    response = client.delete(f"/users/alice/entries/{created['id']}", headers=headers)

    assert response.status_code == 204, response.text
    assert _fetch_entry(created["id"]) is None
