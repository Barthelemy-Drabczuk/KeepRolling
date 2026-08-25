"""Tests for REQ-ANALYTICS-1..4 (see BUSINESS.md).

All of these are characterization tests: the three analytics endpoints in
``app.py`` and the pure functions they delegate to in ``analytics.py`` are
already implemented, so every test here is expected to pass as written.

Everything is exercised through the HTTP endpoints rather than by importing
``analytics.py`` directly, so the auth/ownership checks in ``app.py`` are part
of what is pinned down.

Two conventions the tests below depend on:

* Mood timestamps are stored naive and compared against
  ``datetime.utcnow()``; ``detect_mood_patterns`` builds its window as
  ``utcnow() - timedelta(days=days) .. utcnow()``. Tests that need a mood
  "inside the window" therefore build timestamps relative to now (see
  ``_recent``) rather than hardcoding calendar dates, and always place them at
  least one day in the past so they can never land after the window's upper
  bound.
* ``/analytics/statistics`` has no implicit window, so tests for it can and do
  use fixed calendar dates.

Test data deliberately avoids ``energy == 0.0`` and ``valence == 0.0``: the
quadrant classifier in ``analytics.py`` tests ``energy > 0`` / ``energy < 0``
with no branch for exactly zero, so a mood at zero energy falls through to
``low_energy_unpleasant``. That is not something any REQ-ANALYTICS-* statement
covers, so it is left unpinned here rather than frozen into a test.
"""

from datetime import UTC, datetime, timedelta

import pytest

# ==================== helpers ====================


def _create_mood(client, headers, username, energy=0.5, valence=0.5, timestamp=None):
    """POST a mood and return the created body, asserting it succeeded."""
    payload = {"energy": energy, "valence": valence}
    if timestamp is not None:
        payload["timestamp"] = timestamp
    response = client.post(f"/users/{username}/moods", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def _recent(days_ago, hour=12):
    """A naive-UTC timestamp ``days_ago`` days back, at ``hour`` o'clock.

    ``days_ago`` must be >= 1 so the result is always in the past regardless of
    the hour requested and the wall-clock time the suite happens to run at.
    """
    assert days_ago >= 1
    base = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days_ago)
    return base.replace(hour=hour, minute=0, second=0, microsecond=0)


def _create_moods_in_window(client, headers, username, specs):
    """Create moods from ``(days_ago, hour, energy, valence)`` tuples.

    Returns the naive timestamps used, in the order given.
    """
    timestamps = []
    for days_ago, hour, energy, valence in specs:
        ts = _recent(days_ago, hour)
        _create_mood(client, headers, username, energy, valence, ts.isoformat())
        timestamps.append(ts)
    return timestamps


def _eight_moods_in_window(client, headers, username, energy=0.5, valence=0.5):
    """Create 8 moods on the last 8 days — enough to clear the 7-mood floor."""
    return _create_moods_in_window(
        client,
        headers,
        username,
        [(days_ago, 12, energy, valence) for days_ago in range(1, 9)],
    )


# ==================== REQ-ANALYTICS-1 ====================


def test_statistics_reports_the_number_of_moods(client, auth_headers):
    """REQ-ANALYTICS-1: total_entries counts the caller's moods."""
    headers = auth_headers("alice")
    for day in range(1, 4):
        _create_mood(client, headers, "alice", timestamp=f"2024-01-0{day}T00:00:00")

    response = client.get("/users/alice/analytics/statistics", headers=headers)

    assert response.status_code == 200, response.text
    assert response.json()["total_entries"] == 3


def test_statistics_reports_the_timestamp_range(client, auth_headers):
    """REQ-ANALYTICS-1: date_range spans the oldest and newest mood."""
    headers = auth_headers("alice")
    _create_mood(client, headers, "alice", timestamp="2024-02-01T00:00:00")
    _create_mood(client, headers, "alice", timestamp="2024-01-01T00:00:00")
    _create_mood(client, headers, "alice", timestamp="2024-03-01T00:00:00")

    response = client.get("/users/alice/analytics/statistics", headers=headers)

    assert response.json()["date_range"] == {
        "start": "2024-01-01T00:00:00",
        "end": "2024-03-01T00:00:00",
    }


def test_statistics_reports_energy_mean_median_stdev_min_max(client, auth_headers):
    """REQ-ANALYTICS-1: the five energy statistics are computed over the moods."""
    headers = auth_headers("alice")
    for energy in (0.2, 0.4, 0.6):
        _create_mood(client, headers, "alice", energy=energy, valence=0.5)

    energy_stats = client.get("/users/alice/analytics/statistics", headers=headers).json()["energy"]

    assert energy_stats["mean"] == pytest.approx(0.4)
    assert energy_stats["median"] == pytest.approx(0.4)
    assert energy_stats["stdev"] == pytest.approx(0.2)
    assert energy_stats["min"] == pytest.approx(0.2)
    assert energy_stats["max"] == pytest.approx(0.6)


def test_statistics_reports_valence_mean_median_stdev_min_max(client, auth_headers):
    """REQ-ANALYTICS-1: the same five statistics are computed for valence."""
    headers = auth_headers("alice")
    for valence in (-0.5, 0.5, 0.5):
        _create_mood(client, headers, "alice", energy=0.5, valence=valence)

    valence_stats = client.get("/users/alice/analytics/statistics", headers=headers).json()[
        "valence"
    ]

    assert valence_stats["mean"] == pytest.approx(1 / 6)
    assert valence_stats["median"] == pytest.approx(0.5)
    assert valence_stats["stdev"] == pytest.approx(0.5773502691896258)
    assert valence_stats["min"] == pytest.approx(-0.5)
    assert valence_stats["max"] == pytest.approx(0.5)


def test_statistics_reports_zero_stdev_for_a_single_mood(client, auth_headers):
    """REQ-ANALYTICS-1: stdev is 0 (not an error) when there is one sample."""
    headers = auth_headers("alice")
    _create_mood(client, headers, "alice", energy=0.3, valence=-0.3)

    body = client.get("/users/alice/analytics/statistics", headers=headers).json()

    assert body["energy"]["stdev"] == 0
    assert body["valence"]["stdev"] == 0


def test_statistics_with_no_moods_reports_zero_entries_and_no_range(client, auth_headers):
    """REQ-ANALYTICS-1: a user with no moods gets an empty, non-error result."""
    headers = auth_headers("alice")

    response = client.get("/users/alice/analytics/statistics", headers=headers)

    assert response.status_code == 200, response.text
    assert response.json() == {"total_entries": 0, "date_range": None, "statistics": None}


def test_statistics_excludes_other_users_moods(client, auth_headers):
    """REQ-ANALYTICS-1: statistics cover the caller's own moods only."""
    alice_headers = auth_headers("alice")
    bob_headers = auth_headers("bob", "bobspassword123")
    _create_mood(client, alice_headers, "alice", energy=0.5, valence=0.5)
    for _ in range(4):
        _create_mood(client, bob_headers, "bob", energy=-1.0, valence=-1.0)

    body = client.get("/users/alice/analytics/statistics", headers=alice_headers).json()

    assert body["total_entries"] == 1
    assert body["energy"]["mean"] == pytest.approx(0.5)


def test_statistics_for_another_username_returns_403(client, auth_headers, make_user):
    """REQ-ANALYTICS-1: reading another user's statistics is forbidden."""
    headers = auth_headers("alice")
    make_user("bob", "bobspassword123")

    response = client.get("/users/bob/analytics/statistics", headers=headers)

    assert response.status_code == 403


def test_statistics_start_date_excludes_earlier_moods(client, auth_headers):
    """REQ-ANALYTICS-1: start_date narrows the result to moods at or after it."""
    headers = auth_headers("alice")
    _create_mood(client, headers, "alice", timestamp="2024-01-01T00:00:00")
    _create_mood(client, headers, "alice", timestamp="2024-02-01T00:00:00")
    _create_mood(client, headers, "alice", timestamp="2024-03-01T00:00:00")

    body = client.get(
        "/users/alice/analytics/statistics?start_date=2024-02-01T00:00:00", headers=headers
    ).json()

    assert body["total_entries"] == 2
    assert body["date_range"]["start"] == "2024-02-01T00:00:00"


def test_statistics_end_date_excludes_later_moods(client, auth_headers):
    """REQ-ANALYTICS-1: end_date narrows the result to moods at or before it."""
    headers = auth_headers("alice")
    _create_mood(client, headers, "alice", timestamp="2024-01-01T00:00:00")
    _create_mood(client, headers, "alice", timestamp="2024-02-01T00:00:00")
    _create_mood(client, headers, "alice", timestamp="2024-03-01T00:00:00")

    body = client.get(
        "/users/alice/analytics/statistics?end_date=2024-02-01T00:00:00", headers=headers
    ).json()

    assert body["total_entries"] == 2
    assert body["date_range"]["end"] == "2024-02-01T00:00:00"


def test_statistics_date_window_narrows_to_the_moods_inside_it(client, auth_headers):
    """REQ-ANALYTICS-1: start_date and end_date together bound the window."""
    headers = auth_headers("alice")
    _create_mood(client, headers, "alice", energy=-1.0, timestamp="2024-01-01T00:00:00")
    _create_mood(client, headers, "alice", energy=0.5, timestamp="2024-02-01T00:00:00")
    _create_mood(client, headers, "alice", energy=1.0, timestamp="2024-03-01T00:00:00")

    body = client.get(
        "/users/alice/analytics/statistics"
        "?start_date=2024-01-15T00:00:00&end_date=2024-02-15T00:00:00",
        headers=headers,
    ).json()

    assert body["total_entries"] == 1
    assert body["energy"]["mean"] == pytest.approx(0.5)


def test_statistics_date_window_bounds_are_inclusive(client, auth_headers):
    """REQ-ANALYTICS-1: a mood exactly on either bound is inside the window."""
    headers = auth_headers("alice")
    _create_mood(client, headers, "alice", timestamp="2024-01-01T00:00:00")
    _create_mood(client, headers, "alice", timestamp="2024-03-01T00:00:00")

    body = client.get(
        "/users/alice/analytics/statistics"
        "?start_date=2024-01-01T00:00:00&end_date=2024-03-01T00:00:00",
        headers=headers,
    ).json()

    assert body["total_entries"] == 2


def test_statistics_window_with_no_moods_reports_zero_entries(client, auth_headers):
    """REQ-ANALYTICS-1: a window containing no moods yields the empty result."""
    headers = auth_headers("alice")
    _create_mood(client, headers, "alice", timestamp="2024-01-01T00:00:00")

    body = client.get(
        "/users/alice/analytics/statistics?start_date=2025-01-01T00:00:00", headers=headers
    ).json()

    assert body == {"total_entries": 0, "date_range": None, "statistics": None}


def test_statistics_also_reports_quadrants_trends_and_most_common_mood(client, auth_headers):
    """Characterization beyond REQ-ANALYTICS-1: the response carries three
    further derived blocks that the requirement does not mention."""
    headers = auth_headers("alice")
    for _ in range(3):
        _create_mood(client, headers, "alice", energy=0.5, valence=0.5)

    body = client.get("/users/alice/analytics/statistics", headers=headers).json()

    quadrants = body["quadrant_distribution"]
    assert quadrants["high_energy_pleasant"] == {"count": 3, "percentage": 100.0}
    assert body["trends"]["overall_trend"] == "stable"
    assert body["most_common_mood"]["quadrant"] == "high_energy_pleasant"


# ==================== REQ-ANALYTICS-2 ====================


def test_patterns_reports_detection_when_the_window_holds_enough_moods(client, auth_headers):
    """REQ-ANALYTICS-2: 7+ moods in the window produce computed patterns."""
    headers = auth_headers("alice")
    _eight_moods_in_window(client, headers, "alice")

    response = client.get("/users/alice/analytics/patterns", headers=headers)

    assert response.status_code == 200, response.text
    assert response.json()["patterns_detected"] is True


def test_patterns_reports_time_of_day_averages(client, auth_headers):
    """REQ-ANALYTICS-2: moods are bucketed into morning/afternoon/evening/night
    with a per-bucket count and average energy and valence."""
    headers = auth_headers("alice")
    _create_moods_in_window(
        client,
        headers,
        "alice",
        [
            (1, 8, 0.4, 0.2),
            (2, 8, 0.6, 0.4),
            (3, 14, 0.2, 0.8),
            (4, 14, 0.4, 0.6),
            (5, 20, -0.2, 0.2),
            (6, 20, -0.4, 0.4),
            (7, 3, -0.6, -0.2),
            (8, 3, -0.8, -0.4),
        ],
    )

    time_of_day = client.get("/users/alice/analytics/patterns", headers=headers).json()[
        "time_of_day"
    ]

    assert time_of_day == {
        "morning": {"count": 2, "avg_energy": 0.5, "avg_valence": 0.3},
        "afternoon": {"count": 2, "avg_energy": 0.3, "avg_valence": 0.7},
        "evening": {"count": 2, "avg_energy": -0.3, "avg_valence": 0.3},
        "night": {"count": 2, "avg_energy": -0.7, "avg_valence": -0.3},
    }


def test_patterns_omits_time_buckets_with_no_moods(client, auth_headers):
    """REQ-ANALYTICS-2: only the time-of-day buckets that hold moods appear."""
    headers = auth_headers("alice")
    _create_moods_in_window(
        client, headers, "alice", [(days_ago, 9, 0.5, 0.5) for days_ago in range(1, 9)]
    )

    time_of_day = client.get("/users/alice/analytics/patterns", headers=headers).json()[
        "time_of_day"
    ]

    assert list(time_of_day) == ["morning"]
    assert time_of_day["morning"]["count"] == 8


def test_patterns_reports_day_of_week_averages(client, auth_headers):
    """REQ-ANALYTICS-2: moods are grouped by weekday name with a count and
    average energy and valence."""
    headers = auth_headers("alice")
    first_day = _create_moods_in_window(
        client, headers, "alice", [(days_ago, 12, 0.5, 0.5) for days_ago in (1, 8, 15, 22)]
    )[0]
    second_day = _create_moods_in_window(
        client, headers, "alice", [(days_ago, 12, -0.5, -0.5) for days_ago in (2, 9, 16, 23)]
    )[0]

    day_of_week = client.get("/users/alice/analytics/patterns", headers=headers).json()[
        "day_of_week"
    ]

    assert day_of_week == {
        first_day.strftime("%A"): {"count": 4, "avg_energy": 0.5, "avg_valence": 0.5},
        second_day.strftime("%A"): {"count": 4, "avg_energy": -0.5, "avg_valence": -0.5},
    }


@pytest.mark.parametrize(
    ("energies", "valences", "expected"),
    [
        ([0.5, 0.6] * 4, [0.5, 0.6] * 4, "low"),
        ([0.5, -0.5] * 4, [0.5, -0.5] * 4, "moderate"),
        ([1.0, -1.0] * 4, [1.0, -1.0] * 4, "high"),
    ],
    ids=["low", "moderate", "high"],
)
def test_patterns_classifies_volatility(client, auth_headers, energies, valences, expected):
    """REQ-ANALYTICS-2: mood fluctuation is classified as low, moderate or high."""
    headers = auth_headers("alice")
    _create_moods_in_window(
        client,
        headers,
        "alice",
        [
            (days_ago, 12, energy, valence)
            for days_ago, energy, valence in zip(range(1, 9), energies, valences, strict=True)
        ],
    )

    volatility = client.get("/users/alice/analytics/patterns", headers=headers).json()["volatility"]

    assert volatility["classification"] == expected


def test_patterns_reports_a_streak_of_three_or_more_same_quadrant_moods(client, auth_headers):
    """REQ-ANALYTICS-2: consecutive moods in one quadrant are reported as a streak."""
    headers = auth_headers("alice")
    # Oldest first: 4 high-energy-pleasant, then 4 low-energy-unpleasant.
    timestamps = _create_moods_in_window(
        client,
        headers,
        "alice",
        [(days_ago, 12, 0.5, 0.5) for days_ago in (8, 7, 6, 5)]
        + [(days_ago, 12, -0.5, -0.5) for days_ago in (4, 3, 2, 1)],
    )

    streaks = client.get("/users/alice/analytics/patterns", headers=headers).json()["streaks"]

    assert streaks["total_streaks"] == 2
    assert streaks["streaks"][0] == {
        "quadrant": "high_energy_pleasant",
        "duration_entries": 4,
        "start_date": timestamps[0].isoformat(),
        "end_date": timestamps[3].isoformat(),
    }
    assert streaks["streaks"][1]["quadrant"] == "low_energy_unpleasant"


def test_patterns_reports_no_streak_for_a_run_of_only_two(client, auth_headers):
    """REQ-ANALYTICS-2: a run shorter than 3 moods is not a streak."""
    headers = auth_headers("alice")
    _create_moods_in_window(
        client,
        headers,
        "alice",
        [(days_ago, 12, 0.5, 0.5) for days_ago in (8, 7)]
        + [(days_ago, 12, -0.5, -0.5) for days_ago in (6, 5)]
        + [(days_ago, 12, 0.5, 0.5) for days_ago in (4, 3)]
        + [(days_ago, 12, -0.5, -0.5) for days_ago in (2, 1)],
    )

    streaks = client.get("/users/alice/analytics/patterns", headers=headers).json()["streaks"]

    assert streaks == {"total_streaks": 0, "streaks": []}


def test_patterns_records_a_run_of_exactly_three_as_a_streak(client, auth_headers):
    """REQ-ANALYTICS-2: the 3-mood threshold for a streak is inclusive."""
    headers = auth_headers("alice")
    _create_moods_in_window(
        client,
        headers,
        "alice",
        [(days_ago, 12, 0.5, 0.5) for days_ago in (8, 7, 6)]
        + [(days_ago, 12, -0.5, -0.5) for days_ago in (5, 4)]
        + [(days_ago, 12, 0.5, 0.5) for days_ago in (3, 2)]
        + [(1, 12, -0.5, -0.5)],
    )

    streaks = client.get("/users/alice/analytics/patterns", headers=headers).json()["streaks"]

    assert streaks["total_streaks"] == 1
    assert streaks["streaks"][0]["duration_entries"] == 3


def test_patterns_ignores_moods_older_than_the_default_window(client, auth_headers):
    """REQ-ANALYTICS-2: the default window is the trailing 30 days."""
    headers = auth_headers("alice")
    _create_moods_in_window(
        client, headers, "alice", [(days_ago, 12, 0.5, 0.5) for days_ago in range(60, 68)]
    )

    body = client.get("/users/alice/analytics/patterns", headers=headers).json()

    assert body["patterns_detected"] is False


def test_patterns_days_parameter_narrows_the_window(client, auth_headers):
    """REQ-ANALYTICS-2: an explicit days value overrides the 30-day default, so
    the same moods that the default window detects fall outside a 3-day one."""
    headers = auth_headers("alice")
    _eight_moods_in_window(client, headers, "alice")
    assert client.get("/users/alice/analytics/patterns", headers=headers).json()[
        "patterns_detected"
    ]

    body = client.get("/users/alice/analytics/patterns?days=3", headers=headers).json()

    assert body["patterns_detected"] is False


def test_patterns_days_parameter_can_widen_the_window(client, auth_headers):
    """REQ-ANALYTICS-2: a days value larger than 30 reaches older moods."""
    headers = auth_headers("alice")
    _create_moods_in_window(
        client, headers, "alice", [(days_ago, 12, 0.5, 0.5) for days_ago in range(60, 68)]
    )

    body = client.get("/users/alice/analytics/patterns?days=90", headers=headers).json()

    assert body["patterns_detected"] is True


def test_patterns_excludes_other_users_moods(client, auth_headers):
    """REQ-ANALYTICS-2: patterns cover the caller's own moods only."""
    alice_headers = auth_headers("alice")
    bob_headers = auth_headers("bob", "bobspassword123")
    _eight_moods_in_window(client, bob_headers, "bob")
    _create_moods_in_window(client, alice_headers, "alice", [(1, 12, 0.5, 0.5)])

    body = client.get("/users/alice/analytics/patterns", headers=alice_headers).json()

    assert body["patterns_detected"] is False


def test_patterns_for_another_username_returns_403(client, auth_headers):
    """REQ-ANALYTICS-2: reading another user's patterns is forbidden."""
    alice_headers = auth_headers("alice")
    bob_headers = auth_headers("bob", "bobspassword123")
    _eight_moods_in_window(client, bob_headers, "bob")

    response = client.get("/users/bob/analytics/patterns", headers=alice_headers)

    assert response.status_code == 403


# ==================== REQ-ANALYTICS-3 ====================


def test_patterns_with_no_moods_reports_patterns_not_detected(client, auth_headers):
    """REQ-ANALYTICS-3: zero moods is below the 7-mood floor."""
    headers = auth_headers("alice")

    response = client.get("/users/alice/analytics/patterns", headers=headers)

    assert response.status_code == 200, response.text
    assert response.json()["patterns_detected"] is False


def test_patterns_with_six_moods_reports_patterns_not_detected(client, auth_headers):
    """REQ-ANALYTICS-3: six moods in the window is still under the threshold."""
    headers = auth_headers("alice")
    _create_moods_in_window(
        client, headers, "alice", [(days_ago, 12, 0.5, 0.5) for days_ago in range(1, 7)]
    )

    body = client.get("/users/alice/analytics/patterns", headers=headers).json()

    assert body["patterns_detected"] is False


def test_patterns_below_the_threshold_carries_an_explanatory_message(client, auth_headers):
    """REQ-ANALYTICS-3: the not-detected response explains why, naming the
    7-entry minimum."""
    headers = auth_headers("alice")
    _create_moods_in_window(
        client, headers, "alice", [(days_ago, 12, 0.5, 0.5) for days_ago in range(1, 7)]
    )

    body = client.get("/users/alice/analytics/patterns", headers=headers).json()

    assert isinstance(body["message"], str)
    assert "7" in body["message"]


def test_patterns_below_the_threshold_omits_computed_pattern_data(client, auth_headers):
    """REQ-ANALYTICS-3: no pattern blocks are returned below the threshold."""
    headers = auth_headers("alice")
    _create_moods_in_window(
        client, headers, "alice", [(days_ago, 12, 0.5, 0.5) for days_ago in range(1, 7)]
    )

    body = client.get("/users/alice/analytics/patterns", headers=headers).json()

    assert set(body) == {"patterns_detected", "message"}


def test_patterns_with_exactly_seven_moods_is_computed(client, auth_headers):
    """REQ-ANALYTICS-3: the 7-mood threshold is inclusive — 7 is enough."""
    headers = auth_headers("alice")
    _create_moods_in_window(
        client, headers, "alice", [(days_ago, 12, 0.5, 0.5) for days_ago in range(1, 8)]
    )

    body = client.get("/users/alice/analytics/patterns", headers=headers).json()

    assert body["patterns_detected"] is True
    assert set(body) == {
        "patterns_detected",
        "time_of_day",
        "day_of_week",
        "volatility",
        "streaks",
    }


# ==================== REQ-ANALYTICS-4 ====================


def test_insights_returns_a_list_of_strings(client, auth_headers):
    """REQ-ANALYTICS-4: the endpoint answers 200 with a list of strings."""
    headers = auth_headers("alice")
    _eight_moods_in_window(client, headers, "alice")

    response = client.get("/users/alice/analytics/insights", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body, list)
    assert all(isinstance(insight, str) and insight for insight in body)


def test_insights_covers_both_energy_and_valence_once_there_are_seven_moods(client, auth_headers):
    """REQ-ANALYTICS-4: 7+ moods produce more than one insight, rather than the
    single 'track more moods' placeholder."""
    headers = auth_headers("alice")
    _eight_moods_in_window(client, headers, "alice")

    body = client.get("/users/alice/analytics/insights", headers=headers).json()

    assert len(body) >= 2


def test_insights_reflect_the_callers_own_mood_values(client, auth_headers):
    """REQ-ANALYTICS-4: the insights are derived from the caller's data — high
    and low average energy do not produce the same text."""
    alice_headers = auth_headers("alice")
    bob_headers = auth_headers("bob", "bobspassword123")
    _eight_moods_in_window(client, alice_headers, "alice", energy=0.9, valence=0.9)
    _eight_moods_in_window(client, bob_headers, "bob", energy=-0.9, valence=-0.9)

    alice_insights = client.get("/users/alice/analytics/insights", headers=alice_headers).json()
    bob_insights = client.get("/users/bob/analytics/insights", headers=bob_headers).json()

    assert alice_insights != bob_insights


def test_insights_ignore_other_users_moods(client, auth_headers):
    """REQ-ANALYTICS-4: another user's moods do not feed the caller's insights."""
    alice_headers = auth_headers("alice")
    bob_headers = auth_headers("bob", "bobspassword123")
    _eight_moods_in_window(client, bob_headers, "bob")

    body = client.get("/users/alice/analytics/insights", headers=alice_headers).json()

    assert len(body) == 1
    assert "track" in body[0].lower()


def test_insights_with_no_moods_prompt_the_user_to_start_tracking(client, auth_headers):
    """REQ-ANALYTICS-4: with no data the caller gets a single prompt, not an error."""
    headers = auth_headers("alice")

    response = client.get("/users/alice/analytics/insights", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body) == 1
    assert "track" in body[0].lower()


def test_insights_below_seven_moods_report_the_entry_count(client, auth_headers):
    """REQ-ANALYTICS-4: under 7 moods, the single insight names how many exist."""
    headers = auth_headers("alice")
    for _ in range(3):
        _create_mood(client, headers, "alice")

    body = client.get("/users/alice/analytics/insights", headers=headers).json()

    assert len(body) == 1
    assert "3" in body[0]


def test_insights_for_another_username_returns_403(client, auth_headers, make_user):
    """REQ-ANALYTICS-4: reading another user's insights is forbidden."""
    headers = auth_headers("alice")
    make_user("bob", "bobspassword123")

    response = client.get("/users/bob/analytics/insights", headers=headers)

    assert response.status_code == 403
