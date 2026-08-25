"""Tests for REQ-MOOD-1..5 (see BUSINESS.md).

REQ-MOOD-1..4 are characterization tests: the behavior they pin down is
already implemented by the mood endpoints in ``app.py``. REQ-MOOD-5 (the
optional ``notes`` field) is not implemented yet, so that section is red by
design and drives the implementation.

A note on REQ-MOOD-4's "belongs to a different user" clause. Every mood
route authorizes before it looks anything up, so the status code depends on
which username sits in the path:

* ``GET /users/bob/moods/{alice_mood_id}`` (caller bob, own username in the
  path, someone else's mood id) is the case REQ-MOOD-4 describes -> 404,
  because no mood with that id exists *for bob*.
* ``GET /users/alice/moods/{alice_mood_id}`` (caller bob, alice's username
  in the path) never reaches the mood lookup at all -> 403, from the same
  self-only rule REQ-MOOD-1/REQ-MOOD-3 state for the collection routes.

Both are covered below so the distinction stays pinned.
"""

from datetime import UTC, datetime, timedelta

import pytest
from conftest import TestingSessionLocal
from models import MoodModel, UserModel


def _fetch_user(username):
    """Read a user row straight from the database, bypassing the API."""
    db = TestingSessionLocal()
    try:
        return db.query(UserModel).filter(UserModel.username == username).first()
    finally:
        db.close()


def _fetch_mood(mood_id):
    """Read a mood row straight from the database, bypassing the API."""
    db = TestingSessionLocal()
    try:
        return db.query(MoodModel).filter(MoodModel.id == mood_id).first()
    finally:
        db.close()


def _count_moods(username):
    user = _fetch_user(username)
    db = TestingSessionLocal()
    try:
        return db.query(MoodModel).filter(MoodModel.user_id == user.id).count()
    finally:
        db.close()


def _create_mood(client, headers, username, energy=0.5, valence=0.5, timestamp=None, notes=None):
    """POST a mood and return the created body, asserting it succeeded."""
    payload = {"energy": energy, "valence": valence}
    if timestamp is not None:
        payload["timestamp"] = timestamp
    if notes is not None:
        payload["notes"] = notes
    response = client.post(f"/users/{username}/moods", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


# ==================== REQ-MOOD-1 ====================


def test_create_mood_returns_201_with_the_stored_mood(client, auth_headers):
    """REQ-MOOD-1: POST /users/{username}/moods answers 201 with the new mood."""
    headers = auth_headers("alice")

    response = client.post(
        "/users/alice/moods", json={"energy": 0.25, "valence": -0.75}, headers=headers
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["energy"] == 0.25
    assert body["valence"] == -0.75
    assert isinstance(body["id"], int)


def test_created_mood_is_owned_by_the_authenticated_caller(client, auth_headers):
    """REQ-MOOD-1: the created mood is attached to the calling user's id."""
    headers = auth_headers("alice")

    body = _create_mood(client, headers, "alice")

    assert body["user_id"] == _fetch_user("alice").id


def test_create_mood_for_another_username_returns_403(client, auth_headers, make_user):
    """REQ-MOOD-1: creating a mood under someone else's username is forbidden."""
    headers = auth_headers("alice")
    make_user("bob", "bobspassword123")

    response = client.post(
        "/users/bob/moods", json={"energy": 0.5, "valence": 0.5}, headers=headers
    )

    assert response.status_code == 403


def test_forbidden_create_stores_no_mood_for_the_other_user(client, auth_headers, make_user):
    """REQ-MOOD-1: a 403'd create leaves the target user with no moods."""
    headers = auth_headers("alice")
    make_user("bob", "bobspassword123")

    client.post("/users/bob/moods", json={"energy": 0.5, "valence": 0.5}, headers=headers)

    assert _count_moods("bob") == 0


@pytest.mark.parametrize(
    "payload",
    [{"valence": 0.5}, {"energy": 0.5}, {}],
    ids=["energy-missing", "valence-missing", "both-missing"],
)
def test_create_mood_requires_both_energy_and_valence(client, auth_headers, payload):
    """REQ-MOOD-1: energy and valence are both required fields."""
    headers = auth_headers("alice")

    response = client.post("/users/alice/moods", json=payload, headers=headers)

    assert response.status_code == 422


@pytest.mark.parametrize("bound", [1.0, -1.0], ids=["upper-bound", "lower-bound"])
def test_create_mood_accepts_energy_at_the_interval_bounds(client, auth_headers, bound):
    """REQ-MOOD-1: energy's [-1.0, 1.0] interval is closed at both ends."""
    headers = auth_headers("alice")

    response = client.post(
        "/users/alice/moods", json={"energy": bound, "valence": 0.0}, headers=headers
    )

    assert response.status_code == 201, response.text
    assert response.json()["energy"] == bound


@pytest.mark.parametrize("bound", [1.0, -1.0], ids=["upper-bound", "lower-bound"])
def test_create_mood_accepts_valence_at_the_interval_bounds(client, auth_headers, bound):
    """REQ-MOOD-1: valence's [-1.0, 1.0] interval is closed at both ends."""
    headers = auth_headers("alice")

    response = client.post(
        "/users/alice/moods", json={"energy": 0.0, "valence": bound}, headers=headers
    )

    assert response.status_code == 201, response.text
    assert response.json()["valence"] == bound


@pytest.mark.parametrize("out_of_range", [1.1, -1.1], ids=["above-max", "below-min"])
def test_create_mood_rejects_energy_outside_the_interval(client, auth_headers, out_of_range):
    """REQ-MOOD-1: an energy outside [-1.0, 1.0] is rejected with 422."""
    headers = auth_headers("alice")

    response = client.post(
        "/users/alice/moods", json={"energy": out_of_range, "valence": 0.0}, headers=headers
    )

    assert response.status_code == 422


@pytest.mark.parametrize("out_of_range", [1.1, -1.1], ids=["above-max", "below-min"])
def test_create_mood_rejects_valence_outside_the_interval(client, auth_headers, out_of_range):
    """REQ-MOOD-1: a valence outside [-1.0, 1.0] is rejected with 422."""
    headers = auth_headers("alice")

    response = client.post(
        "/users/alice/moods", json={"energy": 0.0, "valence": out_of_range}, headers=headers
    )

    assert response.status_code == 422


def test_rejected_out_of_range_mood_is_not_persisted(client, auth_headers):
    """REQ-MOOD-1: a 422'd create writes no mood row."""
    headers = auth_headers("alice")

    client.post("/users/alice/moods", json={"energy": 1.1, "valence": 0.0}, headers=headers)

    assert _count_moods("alice") == 0


# ==================== REQ-MOOD-2 ====================


def test_created_mood_timestamp_defaults_to_now_in_utc(client, auth_headers):
    """REQ-MOOD-2: an omitted timestamp defaults to the current UTC time."""
    headers = auth_headers("alice")
    # app.py stores a naive datetime.utcnow(); compare on the same naive-UTC
    # footing without re-introducing the deprecated call here.
    before = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1)

    body = _create_mood(client, headers, "alice")

    after = datetime.now(UTC).replace(tzinfo=None) + timedelta(seconds=1)
    assert before <= datetime.fromisoformat(body["timestamp"]) <= after


def test_supplied_timestamp_is_returned_unchanged(client, auth_headers):
    """REQ-MOOD-2: an explicitly supplied timestamp is honored, not overwritten."""
    headers = auth_headers("alice")

    body = _create_mood(client, headers, "alice", timestamp="2020-01-02T03:04:05")

    assert datetime.fromisoformat(body["timestamp"]) == datetime(2020, 1, 2, 3, 4, 5)


def test_supplied_timestamp_is_persisted_as_given(client, auth_headers):
    """REQ-MOOD-2: the supplied timestamp is what lands in the database."""
    headers = auth_headers("alice")

    body = _create_mood(client, headers, "alice", timestamp="2020-01-02T03:04:05")

    assert _fetch_mood(body["id"]).timestamp == datetime(2020, 1, 2, 3, 4, 5)


# ==================== REQ-MOOD-3 ====================


def test_list_moods_returns_the_callers_own_moods(client, auth_headers):
    """REQ-MOOD-3: GET /users/{username}/moods lists that caller's moods."""
    headers = auth_headers("alice")
    _create_mood(client, headers, "alice", energy=0.1, valence=0.2)
    _create_mood(client, headers, "alice", energy=0.3, valence=0.4)

    response = client.get("/users/alice/moods", headers=headers)

    assert response.status_code == 200, response.text
    listed = {(m["energy"], m["valence"]) for m in response.json()}
    assert listed == {(0.1, 0.2), (0.3, 0.4)}


def test_list_moods_excludes_other_users_moods(client, auth_headers):
    """REQ-MOOD-3: another user's moods never appear in the caller's list."""
    alice_headers = auth_headers("alice")
    bob_headers = auth_headers("bob", "bobspassword123")
    _create_mood(client, bob_headers, "bob", energy=-0.9, valence=-0.9)
    _create_mood(client, alice_headers, "alice", energy=0.1, valence=0.2)

    response = client.get("/users/alice/moods", headers=alice_headers)

    assert [(m["energy"], m["valence"]) for m in response.json()] == [(0.1, 0.2)]


def test_list_moods_for_another_username_returns_403(client, auth_headers, make_user):
    """REQ-MOOD-3: listing another user's moods is forbidden."""
    headers = auth_headers("alice")
    make_user("bob", "bobspassword123")

    response = client.get("/users/bob/moods", headers=headers)

    assert response.status_code == 403


def test_list_moods_is_ordered_newest_first(client, auth_headers):
    """REQ-MOOD-3: moods come back in descending timestamp order."""
    headers = auth_headers("alice")
    _create_mood(client, headers, "alice", energy=0.1, timestamp="2024-01-01T00:00:00")
    _create_mood(client, headers, "alice", energy=0.3, timestamp="2024-03-01T00:00:00")
    _create_mood(client, headers, "alice", energy=0.2, timestamp="2024-02-01T00:00:00")

    response = client.get("/users/alice/moods", headers=headers)

    assert [m["timestamp"] for m in response.json()] == [
        "2024-03-01T00:00:00",
        "2024-02-01T00:00:00",
        "2024-01-01T00:00:00",
    ]


def test_list_moods_limit_caps_the_number_returned(client, auth_headers):
    """REQ-MOOD-3: limit returns only that many moods, newest first."""
    headers = auth_headers("alice")
    for day in range(1, 6):
        _create_mood(client, headers, "alice", timestamp=f"2024-01-0{day}T00:00:00")

    response = client.get("/users/alice/moods?limit=2", headers=headers)

    assert [m["timestamp"] for m in response.json()] == [
        "2024-01-05T00:00:00",
        "2024-01-04T00:00:00",
    ]


def test_list_moods_skip_offsets_into_the_newest_first_order(client, auth_headers):
    """REQ-MOOD-3: skip drops that many of the newest moods before limiting."""
    headers = auth_headers("alice")
    for day in range(1, 6):
        _create_mood(client, headers, "alice", timestamp=f"2024-01-0{day}T00:00:00")

    response = client.get("/users/alice/moods?skip=2&limit=2", headers=headers)

    assert [m["timestamp"] for m in response.json()] == [
        "2024-01-03T00:00:00",
        "2024-01-02T00:00:00",
    ]


def test_list_moods_skip_past_the_end_returns_an_empty_list(client, auth_headers):
    """REQ-MOOD-3: skipping beyond the last mood yields no results."""
    headers = auth_headers("alice")
    _create_mood(client, headers, "alice")

    response = client.get("/users/alice/moods?skip=5", headers=headers)

    assert response.status_code == 200, response.text
    assert response.json() == []


def test_list_moods_without_pagination_params_returns_every_mood(client, auth_headers):
    """REQ-MOOD-3: with no skip/limit given, a small set comes back in full."""
    headers = auth_headers("alice")
    for day in range(1, 6):
        _create_mood(client, headers, "alice", timestamp=f"2024-01-0{day}T00:00:00")

    response = client.get("/users/alice/moods", headers=headers)

    assert len(response.json()) == 5


# ==================== REQ-MOOD-4 ====================


def test_get_unknown_mood_id_returns_404(client, auth_headers):
    """REQ-MOOD-4: GET on a mood id that exists for nobody answers 404."""
    headers = auth_headers("alice")

    response = client.get("/users/alice/moods/9999", headers=headers)

    assert response.status_code == 404


def test_update_unknown_mood_id_returns_404(client, auth_headers):
    """REQ-MOOD-4: PUT on a mood id that exists for nobody answers 404."""
    headers = auth_headers("alice")

    response = client.put(
        "/users/alice/moods/9999", json={"energy": 0.1, "valence": 0.1}, headers=headers
    )

    assert response.status_code == 404


def test_delete_unknown_mood_id_returns_404(client, auth_headers):
    """REQ-MOOD-4: DELETE on a mood id that exists for nobody answers 404."""
    headers = auth_headers("alice")

    response = client.delete("/users/alice/moods/9999", headers=headers)

    assert response.status_code == 404


def test_get_another_users_mood_id_under_own_username_returns_404(client, auth_headers):
    """REQ-MOOD-4: a mood id owned by someone else does not exist for the caller."""
    alice_headers = auth_headers("alice")
    bob_headers = auth_headers("bob", "bobspassword123")
    alice_mood = _create_mood(client, alice_headers, "alice")

    response = client.get(f"/users/bob/moods/{alice_mood['id']}", headers=bob_headers)

    assert response.status_code == 404


def test_update_another_users_mood_id_under_own_username_returns_404(client, auth_headers):
    """REQ-MOOD-4: PUT cannot reach a mood id owned by another user."""
    alice_headers = auth_headers("alice")
    bob_headers = auth_headers("bob", "bobspassword123")
    alice_mood = _create_mood(client, alice_headers, "alice")

    response = client.put(
        f"/users/bob/moods/{alice_mood['id']}",
        json={"energy": -1.0, "valence": -1.0},
        headers=bob_headers,
    )

    assert response.status_code == 404


def test_failed_cross_user_update_leaves_the_mood_unchanged(client, auth_headers):
    """REQ-MOOD-4: the 404'd update does not mutate the owner's mood."""
    alice_headers = auth_headers("alice")
    bob_headers = auth_headers("bob", "bobspassword123")
    alice_mood = _create_mood(client, alice_headers, "alice", energy=0.5, valence=0.5)

    client.put(
        f"/users/bob/moods/{alice_mood['id']}",
        json={"energy": -1.0, "valence": -1.0},
        headers=bob_headers,
    )

    stored = _fetch_mood(alice_mood["id"])
    assert (stored.energy, stored.valence) == (0.5, 0.5)


def test_delete_another_users_mood_id_under_own_username_returns_404(client, auth_headers):
    """REQ-MOOD-4: DELETE cannot reach a mood id owned by another user."""
    alice_headers = auth_headers("alice")
    bob_headers = auth_headers("bob", "bobspassword123")
    alice_mood = _create_mood(client, alice_headers, "alice")

    response = client.delete(f"/users/bob/moods/{alice_mood['id']}", headers=bob_headers)

    assert response.status_code == 404


def test_failed_cross_user_delete_leaves_the_mood_in_place(client, auth_headers):
    """REQ-MOOD-4: the 404'd delete does not remove the owner's mood."""
    alice_headers = auth_headers("alice")
    bob_headers = auth_headers("bob", "bobspassword123")
    alice_mood = _create_mood(client, alice_headers, "alice")

    client.delete(f"/users/bob/moods/{alice_mood['id']}", headers=bob_headers)

    assert _fetch_mood(alice_mood["id"]) is not None


@pytest.mark.parametrize("method", ["get", "put", "delete"])
def test_reaching_a_mood_through_another_users_path_returns_403(client, auth_headers, method):
    """REQ-MOOD-4 boundary: the owner's username in the path is refused before
    the mood lookup, so it is 403 rather than the 404 above."""
    alice_headers = auth_headers("alice")
    bob_headers = auth_headers("bob", "bobspassword123")
    alice_mood = _create_mood(client, alice_headers, "alice")
    url = f"/users/alice/moods/{alice_mood['id']}"

    if method == "put":
        response = client.put(url, json={"energy": 0.1, "valence": 0.1}, headers=bob_headers)
    else:
        response = getattr(client, method)(url, headers=bob_headers)

    assert response.status_code == 403


def test_owner_can_still_get_their_own_mood_by_id(client, auth_headers):
    """REQ-MOOD-4: the 404 rule is scoped — the real owner reads their mood fine."""
    headers = auth_headers("alice")
    created = _create_mood(client, headers, "alice", energy=0.25, valence=-0.25)

    response = client.get(f"/users/alice/moods/{created['id']}", headers=headers)

    assert response.status_code == 200, response.text
    assert response.json()["id"] == created["id"]


# ==================== REQ-MOOD-5 ====================
#
# Unlike everything above, these are *not* characterization tests: `notes` does
# not exist yet on MoodModel, the Mood schemas, or the create/update endpoints.
# They are expected to fail until it does.


def test_create_mood_returns_the_notes_it_was_given(client, auth_headers):
    """REQ-MOOD-5: a notes string supplied on create comes back unchanged."""
    headers = auth_headers("alice")

    response = client.post(
        "/users/alice/moods",
        json={"energy": 0.1, "valence": 0.2, "notes": "Slept badly, coffee helped."},
        headers=headers,
    )

    assert response.status_code == 201, response.text
    assert response.json()["notes"] == "Slept badly, coffee helped."


def test_created_notes_are_persisted(client, auth_headers):
    """REQ-MOOD-5: the notes supplied on create land in the database row."""
    headers = auth_headers("alice")

    body = _create_mood(client, headers, "alice", notes="Walked by the river.")

    assert _fetch_mood(body["id"]).notes == "Walked by the river."


def test_create_mood_without_notes_is_accepted(client, auth_headers):
    """REQ-MOOD-5: notes is optional — omitting it still creates the mood."""
    headers = auth_headers("alice")

    response = client.post(
        "/users/alice/moods", json={"energy": 0.1, "valence": 0.2}, headers=headers
    )

    assert response.status_code == 201, response.text


def test_mood_created_without_notes_has_null_notes(client, auth_headers):
    """REQ-MOOD-5: an omitted notes field reads back as null, not an empty string."""
    headers = auth_headers("alice")

    body = _create_mood(client, headers, "alice")

    assert body["notes"] is None


def test_update_mood_can_set_notes_on_a_mood_created_without_them(client, auth_headers):
    """REQ-MOOD-5: PUT can add notes to a mood that had none."""
    headers = auth_headers("alice")
    created = _create_mood(client, headers, "alice")

    response = client.put(
        f"/users/alice/moods/{created['id']}",
        json={"energy": 0.1, "valence": 0.2, "notes": "Added later."},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["notes"] == "Added later."


def test_update_mood_can_change_existing_notes(client, auth_headers):
    """REQ-MOOD-5: PUT replaces previously stored notes with the new value."""
    headers = auth_headers("alice")
    created = _create_mood(client, headers, "alice", notes="First take.")

    response = client.put(
        f"/users/alice/moods/{created['id']}",
        json={"energy": 0.1, "valence": 0.2, "notes": "Second take."},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["notes"] == "Second take."


def test_updated_notes_are_persisted(client, auth_headers):
    """REQ-MOOD-5: the notes supplied on update land in the database row."""
    headers = auth_headers("alice")
    created = _create_mood(client, headers, "alice", notes="First take.")

    client.put(
        f"/users/alice/moods/{created['id']}",
        json={"energy": 0.1, "valence": 0.2, "notes": "Second take."},
        headers=headers,
    )

    assert _fetch_mood(created["id"]).notes == "Second take."


def test_create_mood_accepts_notes_of_exactly_1000_characters(client, auth_headers):
    """REQ-MOOD-5: "up to 1000 characters" includes the 1000-character case."""
    headers = auth_headers("alice")
    notes = "n" * 1000

    response = client.post(
        "/users/alice/moods",
        json={"energy": 0.1, "valence": 0.2, "notes": notes},
        headers=headers,
    )

    assert response.status_code == 201, response.text
    assert response.json()["notes"] == notes


def test_create_mood_rejects_notes_longer_than_1000_characters(client, auth_headers):
    """REQ-MOOD-5: 1001 characters is over the bound and is rejected with 422."""
    headers = auth_headers("alice")

    response = client.post(
        "/users/alice/moods",
        json={"energy": 0.1, "valence": 0.2, "notes": "n" * 1001},
        headers=headers,
    )

    assert response.status_code == 422


def test_over_length_notes_are_not_persisted(client, auth_headers):
    """REQ-MOOD-5: a create rejected for over-long notes writes no mood row."""
    headers = auth_headers("alice")

    client.post(
        "/users/alice/moods",
        json={"energy": 0.1, "valence": 0.2, "notes": "n" * 1001},
        headers=headers,
    )

    assert _count_moods("alice") == 0


def test_update_mood_accepts_notes_of_exactly_1000_characters(client, auth_headers):
    """REQ-MOOD-5: the 1000-character bound is closed on update too."""
    headers = auth_headers("alice")
    created = _create_mood(client, headers, "alice")
    notes = "n" * 1000

    response = client.put(
        f"/users/alice/moods/{created['id']}",
        json={"energy": 0.1, "valence": 0.2, "notes": notes},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["notes"] == notes


def test_update_mood_rejects_notes_longer_than_1000_characters(client, auth_headers):
    """REQ-MOOD-5: an over-long notes value on update is rejected with 422."""
    headers = auth_headers("alice")
    created = _create_mood(client, headers, "alice")

    response = client.put(
        f"/users/alice/moods/{created['id']}",
        json={"energy": 0.1, "valence": 0.2, "notes": "n" * 1001},
        headers=headers,
    )

    assert response.status_code == 422
