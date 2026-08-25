"""Tests for REQ-EXPORT-1..4 and KD-1 (see BUSINESS.md).

Unlike ``test_analytics.py``, most of this file is *not* characterization: KD-1
records a live defect in the three export endpoints of ``app.py``. They read
``mood.mood`` off ``MoodModel`` and ``entry.mood`` off ``EntryModel``; the
former was never a stored column and the latter must come from the entry's
linked mood. Every export of a non-empty mood/entry list therefore raises
``AttributeError`` at request time today, so the tests below that create data
before exporting are expected to be red until that is fixed.

The corrected behavior these tests pin down, per REQ-EXPORT-1/2/3 + KD-1:

* a mood's exported ``mood`` value is the quadrant label derived from its
  energy/valence, i.e. exactly what ``analytics.get_mood_quadrant_name``
  returns for that pair — it is not read from a column;
* an entry's exported ``mood`` value is its linked mood's quadrant label when
  ``mood_id`` is set (REQ-ENTRY-5), and is null/absent when it is not.

The CSV and JSON exports of an *empty* mood list already work, since the
``AttributeError`` only fires inside the per-row loop; those are kept green as
a regression guard that fixing the non-empty case is not at their expense. The
``start_date``/``end_date`` parse failures (REQ-EXPORT-4) are likewise already
green, being rejected before any row is touched.

The PDF export is the exception: it fails for an empty mood list too, and for a
different reason than KD-1 records. ``export_moods_pdf`` calls
``calculate_mood_statistics(db, user.id, days=None)``, but that function's
signature is ``(db, user_id, start_date=None, end_date=None)`` — so the call
raises ``TypeError: ... unexpected keyword argument 'days'`` before the mood
loop is ever reached. Both PDF tests below are therefore red on that TypeError
first and on KD-1's AttributeError second; REQ-EXPORT-3 needs both fixed.

Quadrant values used here avoid ``energy == 0.0``/``valence == 0.0`` for the
same reason ``test_analytics.py`` does: the classifier has no branch for
exactly zero, and no requirement covers that case.
"""

import csv
import io

import pytest

EXPORT_PATHS = ["csv", "json", "pdf"]

# (energy, valence, expected quadrant label) per analytics.get_mood_quadrant_name
QUADRANT_CASES = [
    (0.5, 0.5, "high_energy_pleasant"),
    (0.5, -0.5, "high_energy_unpleasant"),
    (-0.5, 0.5, "low_energy_pleasant"),
    (-0.5, -0.5, "low_energy_unpleasant"),
    (0.05, 0.05, "neutral"),
]


# ==================== helpers ====================


def _create_mood(client, headers, username, energy=0.5, valence=0.5, notes=None):
    """POST a mood and return the created body, asserting it succeeded."""
    payload = {"energy": energy, "valence": valence}
    if notes is not None:
        payload["notes"] = notes
    response = client.post(f"/users/{username}/moods", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def _create_entry(client, headers, username, content, mood_id=None):
    """POST a journal entry, optionally linked to a mood, and return the body."""
    payload = {"content": content}
    if mood_id is not None:
        payload["mood_id"] = mood_id
    response = client.post(f"/users/{username}/entries", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def _csv_rows(response):
    """Parse a CSV export response body into a list of dict rows."""
    return list(csv.DictReader(io.StringIO(response.text)))


# ==================== REQ-EXPORT-1: CSV ====================


def test_csv_export_succeeds_for_a_non_empty_mood_list(client, auth_headers):
    """A user with at least one mood can export CSV without a server error."""
    headers = auth_headers()
    _create_mood(client, headers, "testuser", energy=0.5, valence=0.5, notes="a note")

    response = client.get("/users/testuser/export/csv", headers=headers)

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")


@pytest.mark.parametrize(("energy", "valence", "expected_label"), QUADRANT_CASES)
def test_csv_mood_column_is_the_quadrant_label(
    client, auth_headers, energy, valence, expected_label
):
    """The CSV ``Mood`` column holds the quadrant derived from energy/valence."""
    headers = auth_headers()
    _create_mood(client, headers, "testuser", energy=energy, valence=valence)

    response = client.get("/users/testuser/export/csv", headers=headers)

    assert response.status_code == 200, response.text
    rows = _csv_rows(response)
    assert len(rows) == 1
    assert rows[0]["Mood"] == expected_label


def test_csv_row_reports_timestamp_energy_and_valence(client, auth_headers):
    """Each CSV row carries the mood's own stored timestamp/energy/valence."""
    headers = auth_headers()
    mood = _create_mood(client, headers, "testuser", energy=0.5, valence=-0.25)

    response = client.get("/users/testuser/export/csv", headers=headers)

    assert response.status_code == 200, response.text
    rows = _csv_rows(response)
    assert len(rows) == 1
    assert float(rows[0]["Energy"]) == 0.5
    assert float(rows[0]["Valence"]) == -0.25
    assert rows[0]["Timestamp"].startswith(mood["timestamp"][:19])


def test_csv_row_reports_the_moods_notes(client, auth_headers):
    """A mood's ``notes`` value is exported verbatim in its CSV row."""
    headers = auth_headers()
    _create_mood(client, headers, "testuser", notes="felt great after a walk")

    response = client.get("/users/testuser/export/csv", headers=headers)

    assert response.status_code == 200, response.text
    rows = _csv_rows(response)
    assert rows[0]["Notes"] == "felt great after a walk"


def test_csv_export_of_another_users_data_is_forbidden(client, auth_headers):
    """Exporting CSV for a username other than the caller's returns 403."""
    other_headers = auth_headers("otheruser", "otherpassword123")
    headers = auth_headers()
    _create_mood(client, headers, "testuser")

    response = client.get("/users/testuser/export/csv", headers=other_headers)

    assert response.status_code == 403


# ==================== REQ-EXPORT-2: JSON ====================


def test_json_export_succeeds_for_a_non_empty_mood_list(client, auth_headers):
    """A user with at least one mood can export JSON without a server error."""
    headers = auth_headers()
    _create_mood(client, headers, "testuser", notes="a note")

    response = client.get("/users/testuser/export/json", headers=headers)

    assert response.status_code == 200, response.text
    assert len(response.json()["moods"]) == 1


@pytest.mark.parametrize(("energy", "valence", "expected_label"), QUADRANT_CASES)
def test_json_mood_field_is_the_quadrant_label(
    client, auth_headers, energy, valence, expected_label
):
    """An exported mood's ``mood`` field is its energy/valence quadrant label."""
    headers = auth_headers()
    _create_mood(client, headers, "testuser", energy=energy, valence=valence)

    response = client.get("/users/testuser/export/json", headers=headers)

    assert response.status_code == 200, response.text
    assert response.json()["moods"][0]["mood"] == expected_label


def test_json_mood_reports_energy_valence_and_notes(client, auth_headers):
    """An exported mood carries its stored energy, valence, and notes."""
    headers = auth_headers()
    _create_mood(client, headers, "testuser", energy=0.5, valence=-0.25, notes="tired")

    response = client.get("/users/testuser/export/json", headers=headers)

    assert response.status_code == 200, response.text
    exported = response.json()["moods"][0]
    assert exported["energy"] == 0.5
    assert exported["valence"] == -0.25
    assert exported["notes"] == "tired"


def test_json_export_omits_entries_by_default(client, auth_headers):
    """Without ``include_entries``, the JSON export has no ``entries`` key."""
    headers = auth_headers()
    mood = _create_mood(client, headers, "testuser")
    _create_entry(client, headers, "testuser", "a journal entry", mood_id=mood["id"])

    response = client.get("/users/testuser/export/json", headers=headers)

    assert response.status_code == 200, response.text
    assert "entries" not in response.json()


def test_json_included_entry_reports_its_linked_moods_quadrant_label(client, auth_headers):
    """An entry linked via ``mood_id`` exports that mood's quadrant label."""
    headers = auth_headers()
    mood = _create_mood(client, headers, "testuser", energy=0.5, valence=0.5)
    _create_entry(client, headers, "testuser", "linked entry", mood_id=mood["id"])

    response = client.get(
        "/users/testuser/export/json",
        params={"include_entries": "true"},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    entries = {entry["content"]: entry for entry in response.json()["entries"]}
    assert entries["linked entry"]["mood"] == "high_energy_pleasant"


def test_json_included_entry_without_a_linked_mood_has_no_mood_label(client, auth_headers):
    """An entry with no ``mood_id`` exports a null (or absent) ``mood`` field."""
    headers = auth_headers()
    mood = _create_mood(client, headers, "testuser", energy=0.5, valence=0.5)
    _create_entry(client, headers, "testuser", "linked entry", mood_id=mood["id"])
    _create_entry(client, headers, "testuser", "unlinked entry")

    response = client.get(
        "/users/testuser/export/json",
        params={"include_entries": "true"},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    entries = {entry["content"]: entry for entry in response.json()["entries"]}
    assert entries["unlinked entry"].get("mood") is None


def test_json_export_of_another_users_data_is_forbidden(client, auth_headers):
    """Exporting JSON for a username other than the caller's returns 403."""
    other_headers = auth_headers("otheruser", "otherpassword123")
    headers = auth_headers()
    _create_mood(client, headers, "testuser")

    response = client.get("/users/testuser/export/json", headers=other_headers)

    assert response.status_code == 403


# ==================== REQ-EXPORT-3: PDF ====================


def test_pdf_export_succeeds_for_a_non_empty_mood_list(client, auth_headers):
    """A user with at least one mood can export a PDF without a server error."""
    headers = auth_headers()
    _create_mood(client, headers, "testuser", energy=0.5, valence=0.5, notes="a note")

    response = client.get("/users/testuser/export/pdf", headers=headers)

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content.startswith(b"%PDF")


def test_pdf_export_of_another_users_data_is_forbidden(client, auth_headers):
    """Exporting a PDF for a username other than the caller's returns 403."""
    other_headers = auth_headers("otheruser", "otherpassword123")
    headers = auth_headers()
    _create_mood(client, headers, "testuser")

    response = client.get("/users/testuser/export/pdf", headers=other_headers)

    assert response.status_code == 403


# ==================== REQ-EXPORT-4: date-range validation ====================


@pytest.mark.parametrize("export_format", EXPORT_PATHS)
@pytest.mark.parametrize("bad_value", ["not-a-date", "2024/01/15", "15-01-2024"])
def test_export_rejects_an_unparseable_start_date(client, auth_headers, export_format, bad_value):
    """A ``start_date`` that is not YYYY-MM-DD returns 400 on every format."""
    headers = auth_headers()

    response = client.get(
        f"/users/testuser/export/{export_format}",
        params={"start_date": bad_value},
        headers=headers,
    )

    assert response.status_code == 400, response.text


@pytest.mark.parametrize("export_format", EXPORT_PATHS)
@pytest.mark.parametrize("bad_value", ["not-a-date", "2024/01/15", "15-01-2024"])
def test_export_rejects_an_unparseable_end_date(client, auth_headers, export_format, bad_value):
    """An ``end_date`` that is not YYYY-MM-DD returns 400 on every format."""
    headers = auth_headers()

    response = client.get(
        f"/users/testuser/export/{export_format}",
        params={"end_date": bad_value},
        headers=headers,
    )

    assert response.status_code == 400, response.text


# ==================== empty-data regression guard ====================


@pytest.mark.parametrize("export_format", EXPORT_PATHS)
def test_export_of_an_empty_mood_list_succeeds(client, auth_headers, export_format):
    """A user with no moods still gets a 200 export in every format.

    Green today for csv/json (KD-1's crash is inside the per-row loop), so
    those two guard against the fix regressing the empty case. The ``pdf``
    parametrization is red for an unrelated reason — see the module docstring's
    note on ``calculate_mood_statistics(..., days=None)``.
    """
    headers = auth_headers()

    response = client.get(f"/users/testuser/export/{export_format}", headers=headers)

    assert response.status_code == 200, response.text


def test_json_export_with_include_entries_and_no_entries_succeeds(client, auth_headers):
    """``include_entries=true`` with no entries yields a 200 and an empty list."""
    headers = auth_headers()

    response = client.get(
        "/users/testuser/export/json",
        params={"include_entries": "true"},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["entries"] == []
