"""Unit tests for ``frontend/history.py``'s pure function (FE-7).

FE-7's history table derives each row's Quadrant column locally rather
than round-tripping to the API, via

    quadrant_label(energy: float, valence: float) -> str

This is the sanctioned local-re-derivation pattern per ARCHITECTURE.md's
Boundaries: ``frontend/`` is a pure HTTP client and must not import
``analytics``, so the classification is duplicated — and because it is
duplicated, it has to match ``analytics.get_mood_quadrant_name``
*exactly*, differing only in presentation (Title Case with spaces
instead of snake_case).

``analytics.get_mood_quadrant_name``'s actual branch order, which these
expectations are taken from rather than guessed at:

    if abs(energy) < 0.1 and abs(valence) < 0.1:  -> "neutral"
    elif energy > 0 and valence > 0:              -> "high_energy_pleasant"
    elif energy > 0 and valence < 0:              -> "high_energy_unpleasant"
    elif energy < 0 and valence > 0:              -> "low_energy_pleasant"
    else:                                         -> "low_energy_unpleasant"

Two consequences of that source worth stating up front, because a
"cleaner" reimplementation gets both wrong:

1. The neutral test is ``<``, not ``<=``. A value of exactly ±0.1 is
   therefore *outside* the neutral band and falls through to the
   quadrant branches. FE-7's "boundary at exactly ±0.1" is pinned in
   both directions below (0.09 neutral, 0.10 not).
2. The final ``else`` is a catch-all, not a genuine low/unpleasant test.
   Any point sitting exactly on an axis but outside the neutral band
   (e.g. energy=0.5, valence=0.0) misses all three strict-inequality
   branches and lands in ``low_energy_unpleasant``. That is a quirk of
   the source, not an accident of these tests; replicating "exact"
   logic means replicating it.

The import is done inside a helper rather than at module scope on
purpose: ``frontend/history.py`` does not exist yet, and a module-scope
import would turn the whole file into a collection error rather than a
set of individually failing tests.
"""

from typing import Callable

NEUTRAL = "Neutral"
HIGH_ENERGY_PLEASANT = "High Energy Pleasant"
HIGH_ENERGY_UNPLEASANT = "High Energy Unpleasant"
LOW_ENERGY_PLEASANT = "Low Energy Pleasant"
LOW_ENERGY_UNPLEASANT = "Low Energy Unpleasant"


def _quadrant_label() -> Callable[[float, float], str]:
    """Return ``frontend.history.quadrant_label``."""
    from frontend.history import quadrant_label

    return quadrant_label


# --- the four quadrants, well outside the neutral band -----------------------


def test_high_energy_pleasant_quadrant_is_labelled() -> None:
    """Positive energy with positive valence reads "High Energy Pleasant"."""
    assert _quadrant_label()(0.8, 0.6) == HIGH_ENERGY_PLEASANT


def test_high_energy_unpleasant_quadrant_is_labelled() -> None:
    """Positive energy with negative valence reads "High Energy Unpleasant"."""
    assert _quadrant_label()(0.8, -0.6) == HIGH_ENERGY_UNPLEASANT


def test_low_energy_pleasant_quadrant_is_labelled() -> None:
    """Negative energy with positive valence reads "Low Energy Pleasant"."""
    assert _quadrant_label()(-0.8, 0.6) == LOW_ENERGY_PLEASANT


def test_low_energy_unpleasant_quadrant_is_labelled() -> None:
    """Negative energy with negative valence reads "Low Energy Unpleasant"."""
    assert _quadrant_label()(-0.8, -0.6) == LOW_ENERGY_UNPLEASANT


# --- the neutral band and its boundary ---------------------------------------


def test_the_origin_is_neutral() -> None:
    """The exact origin mood (0.0, 0.0) reads "Neutral", not a quadrant name."""
    assert _quadrant_label()(0.0, 0.0) == NEUTRAL


def test_just_inside_the_neutral_band_is_neutral() -> None:
    """(0.09, 0.09) is inside abs(...) < 0.1 on both axes, so it reads "Neutral"."""
    assert _quadrant_label()(0.09, 0.09) == NEUTRAL


def test_exactly_positive_one_tenth_is_not_neutral() -> None:
    """abs(...) < 0.1 excludes 0.1 itself: (0.1, 0.1) is a quadrant, not "Neutral"."""
    assert _quadrant_label()(0.1, 0.1) == HIGH_ENERGY_PLEASANT


def test_exactly_negative_one_tenth_is_not_neutral() -> None:
    """abs(...) < 0.1 excludes -0.1 too: (-0.1, -0.1) is a quadrant, not "Neutral"."""
    assert _quadrant_label()(-0.1, -0.1) == LOW_ENERGY_UNPLEASANT


def test_one_axis_at_the_boundary_leaves_the_neutral_band() -> None:
    """Neutral needs *both* axes inside the band: energy 0.1 with valence 0.0 is not neutral."""
    assert _quadrant_label()(0.1, 0.0) != NEUTRAL


# --- the source's catch-all else, replicated verbatim ------------------------


def test_a_point_on_the_valence_axis_falls_through_to_low_energy_unpleasant() -> None:
    """High energy with exactly zero valence hits get_mood_quadrant_name's catch-all else.

    None of ``energy > 0 and valence > 0``, ``energy > 0 and valence < 0``
    or ``energy < 0 and valence > 0`` holds when valence is exactly 0.0,
    so analytics.py returns "low_energy_unpleasant" for a *high*-energy
    mood. quadrant_label replicates that rather than correcting it.
    """
    assert _quadrant_label()(0.5, 0.0) == LOW_ENERGY_UNPLEASANT
