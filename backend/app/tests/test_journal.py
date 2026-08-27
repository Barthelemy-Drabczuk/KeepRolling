"""Unit tests for ``frontend/journal.py``'s pure functions (FE-8c).

FE-8a and FE-8b deliberately introduced no tests in this file (their
verification lives in ``tests/test_frontend.py`` against the rendered
page); these are therefore the first tests here, and they cover only the
two pure functions FE-8c adds:

    mood_option_label(mood: dict) -> str
    mood_line(mood: dict | None) -> str

Both delegate their quadrant naming to ``frontend.history.quadrant_label``
(imported, per FE-8c, as ``from .history import quadrant_label`` — a
sibling ``frontend/`` import, not a re-copy), so the expected strings
below are taken from that function's actual behavior as pinned by
``tests/test_history.py``: Title Case with spaces, and a "Neutral" band of
``abs(energy) < 0.1 and abs(valence) < 0.1`` (strictly ``<``).

Everything else in FE-8c — the ``ui.select``'s population, ``mood_id``
reaching the POST body, the third card label, the ``null``/outside-window
cases, and the moods-fetch degradation branch — is
manual-verification-only per ARCHITECTURE.md's Testing policy.

The imports are done inside helpers rather than at module scope on
purpose: neither function exists in ``frontend/journal.py`` yet, and a
module-scope import would turn the whole file into a collection error
rather than a set of individually failing tests.

Note the two non-ASCII separators, which are load-bearing and asserted
verbatim: ``mood_option_label`` joins timestamp and quadrant with an em
dash (U+2014), while ``mood_line`` separates the two coordinates with a
middle dot (U+00B7), matching ``mood_pad._readout``'s existing
``f"Energy: {energy:.2f} · Valence: {valence:.2f}"`` convention.
"""

from typing import Callable

# A MoodResponse-shaped payload as the API returns it: naive-UTC ISO
# timestamp, floats in -1.0..1.0, optional notes.
HIGH_ENERGY_PLEASANT_MOOD = {
    "id": 7,
    "timestamp": "2026-08-27T09:00:00",
    "energy": 0.80,
    "valence": 0.60,
    "notes": "good morning",
}

NEUTRAL_MOOD = {
    "id": 8,
    "timestamp": "2026-08-27T13:45:00",
    "energy": 0.05,
    "valence": -0.05,
    "notes": None,
}


def _mood_line() -> Callable[[dict | None], str]:
    """Return ``frontend.journal.mood_line``."""
    from frontend.journal import mood_line

    return mood_line


def _mood_option_label() -> Callable[[dict], str]:
    """Return ``frontend.journal.mood_option_label``."""
    from frontend.journal import mood_option_label

    return mood_option_label


# --- mood_line ---------------------------------------------------------------


def test_mood_line_is_empty_when_no_mood_is_linked() -> None:
    """An entry with no linked mood yields "", so the card creates no third label."""
    assert _mood_line()(None) == ""


def test_mood_line_names_the_quadrant_and_both_coordinates() -> None:
    """A linked mood renders as "Mood: <quadrant> (Energy: e · Valence: v)"."""
    assert (
        _mood_line()(HIGH_ENERGY_PLEASANT_MOOD)
        == "Mood: High Energy Pleasant (Energy: 0.80 · Valence: 0.60)"
    )


def test_mood_line_calls_a_near_origin_mood_neutral() -> None:
    """A mood inside quadrant_label's neutral band reads "Neutral", not a quadrant name."""
    assert _mood_line()(NEUTRAL_MOOD) == "Mood: Neutral (Energy: 0.05 · Valence: -0.05)"


def test_mood_line_pads_coordinates_to_two_decimals() -> None:
    """A coordinate with fewer than two decimals is zero-padded, not printed bare."""
    mood = {"id": 9, "timestamp": "2026-08-27T09:00:00", "energy": 0.5, "valence": -0.2}
    assert _mood_line()(mood) == "Mood: High Energy Unpleasant (Energy: 0.50 · Valence: -0.20)"


def test_mood_line_rounds_coordinates_to_two_decimals() -> None:
    """A coordinate with more than two decimals is rounded to two, not truncated."""
    mood = {
        "id": 10,
        "timestamp": "2026-08-27T09:00:00",
        "energy": 0.666,
        "valence": -0.334,
    }
    assert _mood_line()(mood) == "Mood: High Energy Unpleasant (Energy: 0.67 · Valence: -0.33)"


# --- mood_option_label -------------------------------------------------------


def test_mood_option_label_joins_the_formatted_timestamp_and_quadrant() -> None:
    """A select option reads "<%Y-%m-%d %H:%M UTC> — <quadrant>", em-dash separated."""
    assert (
        _mood_option_label()(HIGH_ENERGY_PLEASANT_MOOD)
        == "2026-08-27 09:00 UTC — High Energy Pleasant"
    )
