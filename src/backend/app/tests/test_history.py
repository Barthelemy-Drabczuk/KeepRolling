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

MC-4 (REQ-UI-9) re-points these expectations at the region-membership
classifier MC-3 (REQ-ANALYTICS-6) put in ``analytics.py``, superseding
MC-2 (REQ-UI-1)'s nearest-anchor mirror. The categories and the Neutral
band are unchanged; only the geometry between them is. The source this
file mirrors is now:

    if abs(energy) < 0.1 and abs(valence) < 0.1:   -> "neutral"
    otherwise: convert the mood to the pad's fixed 400x400 pixel space,
    x = (valence + 1) * 200 and y = (1 - energy) * 200, and return the
    first zone whose rectangle contains (x, y), both interval ends
    closed, testing the table below in order; a point matching no row is
    "energetic_optimism".

The table, a literal transcription of ``frontend/pad_art.py``'s
``_ZONE_SHAPES`` in the *reverse* of that module's SVG paint order, so
the last-painted (visually topmost) zone is tested first. Re-typed here
rather than imported: the Boundaries rule above is why the duplication
exists in the first place.

    zone                  x_min  x_max  y_min  y_max   caption
    deep_despair              0     66    338    400   "Mom would be sad"
    peak_excitement         336    400      0     60   "Let's fucking goooo"
    resigned_acceptance       0    266    130    200   "It is what it is" (band A)
    resigned_acceptance     204    266    200    400   "It is what it is" (band B)
    relaxed_contentment     266    400    200    400   "We vibing"
    sinking_despair           0    204    200    400   "It's so over"
    reckless_energy           0    200      0    130   "Fuck it we ball"
    (no match)                                         "We are so fucking back"

Three consequences of that source worth stating up front, because a
"cleaner" reimplementation gets them wrong:

1. The pixel mapping consumes ``valence`` as x and ``energy`` as y while
   the function's parameters are ``(energy, valence)``. The zone map is
   not symmetric about the ``valence = energy`` diagonal, but several
   points below still classify the same either way — the cases that
   catch a swapped pair are the ``reckless_energy`` and
   ``relaxed_contentment`` representative points, which are each other's
   mirror image, and the on-axis case ``(0.5, 0.0)``.
2. The neutral test is ``<``, not ``<=``, on *both* axes. A value of
   exactly ±0.1 is therefore outside the neutral band and falls through
   to whichever zone is painted over it; that boundary is pinned in both
   directions below (0.09 neutral, 0.10 not).
3. Closed intervals plus reverse-paint-order-first-match-wins *is* the
   boundary convention — a mood exactly on an edge or corner two zones
   share belongs to the later-painted one, the one that visually covers
   that pixel. There is no separate tiebreak rule, and there is no
   catch-all ``else`` on an axis: a point sitting exactly on an axis but
   outside the neutral band (e.g. energy=0.5, valence=0.0, pad x=200) is
   resolved by that same convention like any other edge point.

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

# label -> one representative point strictly inside its painted zone, in
# (valence, energy). Four are the caption positions MC-2 used as anchors,
# kept because they still land inside the zone they name; the other three
# (peak_excitement, resigned_acceptance, deep_despair) had to move, because
# the 2026-09-09 pad redesign left their old anchor outside their own zone.
# The same seven points MC-3 pinned in tests/test_analytics.py.
ZONE_INTERIOR_POINTS = {
    RECKLESS_ENERGY: (-0.50, 0.50),
    ENERGETIC_OPTIMISM: (0.45, 0.35),
    PEAK_EXCITEMENT: (0.75, 0.80),
    RESIGNED_ACCEPTANCE: (-0.33, 0.15),
    SINKING_DESPAIR: (-0.50, -0.50),
    DEEP_DESPAIR: (-0.85, -0.85),
    RELAXED_CONTENTMENT: (0.50, -0.50),
}

ALL_LABELS = set(ZONE_INTERIOR_POINTS) | {NEUTRAL}


def _quadrant_label() -> Callable[[float, float], str]:
    """Return ``frontend.history.quadrant_label``."""
    from frontend.history import quadrant_label

    return quadrant_label


def _pad_grid(step: float = 0.02) -> list[tuple[float, float]]:
    """Every ``(energy, valence)`` point on a fine grid over [-1, 1] x [-1, 1]."""
    axis = [round(-1.0 + index * step, 10) for index in range(int(2 / step) + 1)]
    return [(energy, valence) for energy in axis for valence in axis]


# --- the seven painted zones -------------------------------------------------


@pytest.mark.parametrize(
    ("label", "point"), sorted(ZONE_INTERIOR_POINTS.items()), ids=sorted(ZONE_INTERIOR_POINTS)
)
def test_each_zones_representative_point_is_labelled_with_its_own_category(
    label: str, point: tuple[float, float]
) -> None:
    """A mood logged strictly inside a painted zone reads that zone's label."""
    valence, energy = point

    assert _quadrant_label()(energy, valence) == label


@pytest.mark.parametrize(
    ("energy", "valence", "expected"),
    [(0.5, 0.5, ENERGETIC_OPTIMISM), (0.75, 0.75, PEAK_EXCITEMENT)],
)
def test_two_points_in_one_quadrant_are_told_apart_by_zone(
    energy: float, valence: float, expected: str
) -> None:
    """Labelling is per painted zone, not per quadrant: two high-energy pleasant
    points resolve to different labels, because "Peak Excitement" is carved out
    of "Energetic Optimism"'s corner."""
    assert _quadrant_label()(energy, valence) == expected


# --- the neutral band and its boundary ---------------------------------------


def test_the_origin_is_neutral() -> None:
    """The exact origin mood (0.0, 0.0) reads "Neutral", not a category name."""
    assert _quadrant_label()(0.0, 0.0) == NEUTRAL


def test_just_inside_the_neutral_band_is_neutral() -> None:
    """(0.09, 0.09) is inside abs(...) < 0.1 on both axes, so it reads "Neutral"."""
    assert _quadrant_label()(0.09, 0.09) == NEUTRAL


def test_exactly_positive_one_tenth_is_not_neutral() -> None:
    """abs(...) < 0.1 excludes 0.1 itself: (0.1, 0.1) is pad pixel (220, 180),
    inside "Resigned Acceptance"'s upper band."""
    assert _quadrant_label()(0.1, 0.1) == RESIGNED_ACCEPTANCE


def test_exactly_negative_one_tenth_is_not_neutral() -> None:
    """abs(...) < 0.1 excludes -0.1 too: (-0.1, -0.1) is pad pixel (180, 220),
    inside "Sinking Despair"."""
    assert _quadrant_label()(-0.1, -0.1) == SINKING_DESPAIR


def test_one_axis_at_the_boundary_leaves_the_neutral_band() -> None:
    """Neutral needs *both* axes inside the band: energy 0.1 with valence 0.0 is not neutral."""
    assert _quadrant_label()(0.1, 0.0) != NEUTRAL


# --- no catch-all branch: on-axis points are classified by zone membership ---


@pytest.mark.parametrize(
    ("energy", "valence", "expected"),
    [(0.5, 0.0, RECKLESS_ENERGY), (0.0, -0.5, RESIGNED_ACCEPTANCE)],
)
def test_a_point_on_an_axis_is_classified_by_zone_membership(
    energy: float, valence: float, expected: str
) -> None:
    """A point with a zero coordinate lands in whichever zone is painted over
    it, like any other point.

    The pre-MC-2 5-category chain had a catch-all ``else`` that swept
    these into "Low Energy Unpleasant" — including *high*-energy moods
    such as (0.5, 0.0). MC-1 removed that quirk from ``analytics.py`` and
    MC-2 removed it here; MC-3/MC-4 keep it removed, and re-value the
    first case: ``valence=0.0`` is pad pixel x=200 exactly, the edge
    "Reckless Energy" (x 0..200) shares with "Energetic Optimism"
    (x 200..400), and "Reckless Energy" is painted later, so it wins.
    """
    assert _quadrant_label()(energy, valence) == expected


# --- the boundary convention -------------------------------------------------


@pytest.mark.parametrize(
    ("energy", "valence", "expected"),
    [
        (0.35, -0.50, RESIGNED_ACCEPTANCE),
        (-0.50, 0.02, RESIGNED_ACCEPTANCE),
        (-0.50, 0.33, RESIGNED_ACCEPTANCE),
    ],
    ids=["y=130_reckless_edge", "x=204_sinking_edge", "x=266_relaxed_edge"],
)
def test_a_point_on_a_shared_zone_edge_belongs_to_the_later_painted_zone(
    energy: float, valence: float, expected: str
) -> None:
    """Closed intervals plus reverse-paint-order-first-match *is* the boundary
    convention here too — a mood exactly on an edge two zones share reads the
    label of whichever was painted later, i.e. the one that visually covers
    that pixel. No separate tiebreak rule exists.

    The three cases are pad pixels (100, 130), (204, 300) and (266, 300): the
    edges "Resigned Acceptance" shares with "Reckless Energy" above it,
    "Sinking Despair" to its left and "Relaxed Contentment" to its right.
    "Resigned Acceptance" is painted after all three. Same three cases as
    ``tests/test_analytics.py``'s backend counterpart, so the mirror is pinned
    on the boundary and not only in each zone's interior.
    """
    assert _quadrant_label()(energy, valence) == expected


# --- the label set as a whole ------------------------------------------------


def test_all_eight_labels_are_reachable_somewhere_on_the_pad() -> None:
    """The eight labels tessellate [-1, 1] x [-1, 1]: every point produces one of
    them, and each of them is produced somewhere — same category set as the
    backend classifier, no more and no fewer."""
    produced = {_quadrant_label()(energy, valence) for energy, valence in _pad_grid()}

    assert produced == ALL_LABELS


# --- FE-9a: quadrant_label splits into classification + presentation ---------
#
# FE-9a's distribution chart needs the two halves separately: the bar
# labels need snake_case -> Title Case without a mood to classify (the
# category names arrive as the API payload's keys), and FE-9c's scatter
# series need the snake_case identifier to look a colour up by. Neither
# can be got from quadrant_label, which does both at once and returns
# only the Title Case string.
#
# So quadrant_label becomes category_label(mood_category(energy, valence)),
# with both halves public. This is behaviour-preserving: quadrant_label's
# output is unchanged, so every test above -- and every mood_line /
# mood_option_label test in tests/test_journal.py, which reach it through
# frontend/journal.py's `from .history import quadrant_label` -- stays
# green untouched.
#
# The alternative was a third copy of MC-1's anchor table inside
# frontend/analytics.py. ARCHITECTURE.md's Boundaries rule sanctions
# exactly *one* local mirror of analytics.get_mood_quadrant_name, so a
# sibling import is the only correct answer here.

SNAKE_CASE_CATEGORIES = {
    "reckless_energy": RECKLESS_ENERGY,
    "deep_despair": DEEP_DESPAIR,
    "neutral": NEUTRAL,
}


def _mood_category() -> Callable[[float, float], str]:
    """Return ``frontend.history.mood_category``."""
    from frontend.history import mood_category

    return mood_category


def _category_label() -> Callable[[str], str]:
    """Return ``frontend.history.category_label``."""
    from frontend.history import category_label

    return category_label


@pytest.mark.parametrize(
    ("energy", "valence", "expected"),
    [
        (0.50, -0.50, "reckless_energy"),
        (-0.85, -0.85, "deep_despair"),
        (0.0, 0.0, "neutral"),
    ],
)
def test_mood_category_returns_the_snake_case_identifier(
    energy: float, valence: float, expected: str
) -> None:
    """The classification half answers the zone's identifier, not the display string.

    Same arguments and same ``(energy, valence)`` order as ``quadrant_label``;
    only the presentation is stripped off. Note the representative points are
    stored ``(valence, energy)``, which is why the first case reads energy 0.50 /
    valence -0.50 for the ``(-0.50, 0.50)`` point.
    """
    assert _mood_category()(energy, valence) == expected


@pytest.mark.parametrize(
    ("category", "expected"),
    sorted(SNAKE_CASE_CATEGORIES.items()),
    ids=sorted(SNAKE_CASE_CATEGORIES),
)
def test_category_label_title_cases_a_snake_case_identifier(category: str, expected: str) -> None:
    """The presentation half turns an identifier into its display label on its own.

    It takes a category name rather than a mood, which is what lets FE-9a
    label the distribution chart's x-axis from the API payload's keys
    without inventing an (energy, valence) pair to classify.
    """
    assert _category_label()(category) == expected
