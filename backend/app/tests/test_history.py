"""Unit tests for ``frontend/history.py``'s pure function (FE-7, MC-2).

FE-7's history table derives each row's Quadrant column locally rather
than round-tripping to the API, via

    quadrant_label(energy: float, valence: float) -> str

This is the sanctioned local-re-derivation pattern per ARCHITECTURE.md's
Boundaries: ``frontend/`` is a pure HTTP client and must not import
``analytics``, so the classification is duplicated — and because it is
duplicated, it has to match ``analytics.get_mood_quadrant_name``
*exactly*, differing only in presentation (Title Case with spaces
instead of snake_case).

MC-2 (REQ-UI-1) re-points these expectations at the 8-category
nearest-anchor classifier MC-1 (REQ-ANALYTICS-5) put in ``analytics.py``,
replacing the previous 5-category ``elif`` chain. The source this file
mirrors is now:

    if abs(energy) < 0.1 and abs(valence) < 0.1:   -> "neutral"
    otherwise: the caption anchor with the smallest squared Euclidean
    distance to (valence, energy), ties broken by the anchor table's
    insertion order.

The seven anchors, in ``(valence, energy)`` order — each caption's
position on the FE-4 mood pad. Re-typed here rather than imported: the
Boundaries rule above is why the duplication exists in the first place.

    reckless_energy      (-0.50,  0.50)   "Fuck it we ball"
    energetic_optimism   ( 0.45,  0.35)   "We are so fucking back"
    peak_excitement      ( 0.60,  0.65)   "Let's fucking goooo"
    resigned_acceptance  (-0.35, -0.35)   "It is what it is"
    sinking_despair      (-0.50, -0.50)   "It's so over"
    deep_despair         (-0.65, -0.65)   "Mom would be sad"
    relaxed_contentment  ( 0.50, -0.50)   "We vibing"

Three consequences of that source worth stating up front, because a
"cleaner" reimplementation gets them wrong:

1. The anchors are ``(valence, energy)`` while the function's parameters
   are ``(energy, valence)``. The anchor set is nearly symmetric about
   the ``valence = energy`` diagonal, so a swapped pair still passes
   several cases below — the two that catch it are the
   ``reckless_energy`` and ``relaxed_contentment`` anchors, which are
   each other's mirror image.
2. The neutral test is ``<``, not ``<=``, on *both* axes. A value of
   exactly ±0.1 is therefore outside the neutral band and is classified
   by distance like any other point; that boundary is pinned in both
   directions below (0.09 neutral, 0.10 not).
3. There is no catch-all branch any more. A point sitting exactly on an
   axis but outside the neutral band (e.g. energy=0.5, valence=0.0) has
   a nearest anchor like every other point — the old classifier's quirk
   of sweeping those into "Low Energy Unpleasant" is gone, and
   ``test_a_point_on_an_axis_is_classified_by_distance`` pins its
   removal rather than its behaviour.

The import is done inside a helper rather than at module scope on
purpose: it keeps a failure in ``frontend/history.py`` a set of
individually failing tests rather than one collection error.
"""

from typing import Callable

import pytest

NEUTRAL = "Neutral"
RECKLESS_ENERGY = "Reckless Energy"
ENERGETIC_OPTIMISM = "Energetic Optimism"
PEAK_EXCITEMENT = "Peak Excitement"
RESIGNED_ACCEPTANCE = "Resigned Acceptance"
SINKING_DESPAIR = "Sinking Despair"
DEEP_DESPAIR = "Deep Despair"
RELAXED_CONTENTMENT = "Relaxed Contentment"

# label -> its caption anchor in (valence, energy), matching the table in
# the module docstring.
CAPTION_ANCHORS = {
    RECKLESS_ENERGY: (-0.50, 0.50),
    ENERGETIC_OPTIMISM: (0.45, 0.35),
    PEAK_EXCITEMENT: (0.60, 0.65),
    RESIGNED_ACCEPTANCE: (-0.35, -0.35),
    SINKING_DESPAIR: (-0.50, -0.50),
    DEEP_DESPAIR: (-0.65, -0.65),
    RELAXED_CONTENTMENT: (0.50, -0.50),
}

ALL_LABELS = set(CAPTION_ANCHORS) | {NEUTRAL}


def _quadrant_label() -> Callable[[float, float], str]:
    """Return ``frontend.history.quadrant_label``."""
    from frontend.history import quadrant_label

    return quadrant_label


def _pad_grid(step: float = 0.02) -> list[tuple[float, float]]:
    """Every ``(energy, valence)`` point on a fine grid over [-1, 1] x [-1, 1]."""
    axis = [round(-1.0 + index * step, 10) for index in range(int(2 / step) + 1)]
    return [(energy, valence) for energy in axis for valence in axis]


# --- the seven caption anchors -----------------------------------------------


@pytest.mark.parametrize(
    ("label", "anchor"), sorted(CAPTION_ANCHORS.items()), ids=sorted(CAPTION_ANCHORS)
)
def test_each_caption_anchor_point_is_labelled_with_its_own_category(
    label: str, anchor: tuple[float, float]
) -> None:
    """A mood logged exactly at a caption's anchor reads that caption's label."""
    valence, energy = anchor

    assert _quadrant_label()(energy, valence) == label


@pytest.mark.parametrize(
    ("energy", "valence", "expected"),
    [(0.5, 0.5, ENERGETIC_OPTIMISM), (0.75, 0.75, PEAK_EXCITEMENT)],
)
def test_two_anchors_in_one_quadrant_are_told_apart_by_distance(
    energy: float, valence: float, expected: str
) -> None:
    """Labelling is per-anchor, not per-quadrant: two high-energy pleasant
    points resolve to different labels."""
    assert _quadrant_label()(energy, valence) == expected


# --- the neutral band and its boundary ---------------------------------------


def test_the_origin_is_neutral() -> None:
    """The exact origin mood (0.0, 0.0) reads "Neutral", not a category name."""
    assert _quadrant_label()(0.0, 0.0) == NEUTRAL


def test_just_inside_the_neutral_band_is_neutral() -> None:
    """(0.09, 0.09) is inside abs(...) < 0.1 on both axes, so it reads "Neutral"."""
    assert _quadrant_label()(0.09, 0.09) == NEUTRAL


def test_exactly_positive_one_tenth_is_not_neutral() -> None:
    """abs(...) < 0.1 excludes 0.1 itself: (0.1, 0.1) is nearest "Energetic Optimism"."""
    assert _quadrant_label()(0.1, 0.1) == ENERGETIC_OPTIMISM


def test_exactly_negative_one_tenth_is_not_neutral() -> None:
    """abs(...) < 0.1 excludes -0.1 too: (-0.1, -0.1) is nearest "Resigned Acceptance"."""
    assert _quadrant_label()(-0.1, -0.1) == RESIGNED_ACCEPTANCE


def test_one_axis_at_the_boundary_leaves_the_neutral_band() -> None:
    """Neutral needs *both* axes inside the band: energy 0.1 with valence 0.0 is not neutral."""
    assert _quadrant_label()(0.1, 0.0) != NEUTRAL


# --- no catch-all branch: on-axis points are classified by distance ----------


@pytest.mark.parametrize(
    ("energy", "valence", "expected"),
    [(0.5, 0.0, ENERGETIC_OPTIMISM), (0.0, -0.5, RESIGNED_ACCEPTANCE)],
)
def test_a_point_on_an_axis_is_classified_by_distance(
    energy: float, valence: float, expected: str
) -> None:
    """A point with a zero coordinate lands on its nearest anchor like any other.

    The previous 5-category chain had a catch-all ``else`` that swept
    these into "Low Energy Unpleasant" — including *high*-energy moods
    such as (0.5, 0.0). MC-1 removed that quirk from ``analytics.py`` and
    MC-2 removes it here; this test replaces the one that used to pin it.
    """
    assert _quadrant_label()(energy, valence) == expected


# --- the label set as a whole ------------------------------------------------


def test_all_eight_labels_are_reachable_somewhere_on_the_pad() -> None:
    """The eight labels tessellate [-1, 1] x [-1, 1]: every point produces one of
    them, and each of them is produced somewhere — same category set as the
    backend classifier, no more and no fewer."""
    produced = {_quadrant_label()(energy, valence) for energy, valence in _pad_grid()}

    assert produced == ALL_LABELS
