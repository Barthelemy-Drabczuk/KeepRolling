"""Unit tests for ``frontend/analytics.py``'s pure functions (FE-9a, REQ-UI-3).

Note the file name. ``tests/test_analytics.py`` is already taken by the
*backend* ``analytics.py`` module's tests, so the frontend analytics
page's tests live here instead. The two modules themselves do not
collide — ``frontend.analytics`` and ``analytics`` are distinct
``sys.modules`` keys and Python 3 has no implicit relative imports, the
same situation ``frontend/auth.py`` and the backend ``auth.py`` have
shipped in since FE-3a — but two files cannot share one path, so this
one is renamed rather than the module.

FE-9a renders the distribution half of the analytics page: a bar chart
of how a user's moods fall across MC-1's eight categories, built from
``GET /users/{username}/analytics/statistics``'s ``quadrant_distribution``
object. That object is produced by ``analytics.calculate_quadrant_
distribution`` and always carries all eight keys, zero counts included,
each valued ``{"count": int, "percentage": float}``.

Only the options-building arithmetic is tested here. The chart itself
sits behind an authenticated fetch, and ``app.storage.user`` cannot be
seeded over HTTP, so the populated chart, the zero-mood-but-logged-in
empty state and both failure branches are manual-verification-only per
ARCHITECTURE.md's Testing policy — and ``nicegui.testing``'s ``user`` /
``Screen`` fixtures are banned repo-wide, so they are not reached for
here. What *is* server-observable about the page (the unguarded route,
the logged-out prompt, the nav link from ``/``) is tested in
``tests/test_frontend.py``.

The colour rule, which is FE-9a's one real design decision: MC-1 left
the classifier with eight categories while FE-2's palette still defines
four colours, and both the MC-1 and MC-2 ARCHITECTURE.md entries forbid
extending that palette (its four entries are the *mood pad's* quadrant
fills). So each category takes the colour of the quadrant its MC-1
anchor falls in:

    reckless_energy      (-0.50,  0.50)  high energy / unpleasant  #783020
    energetic_optimism   ( 0.45,  0.35)  high energy / pleasant    #e0c080
    peak_excitement      ( 0.60,  0.65)  high energy / pleasant    #e0c080
    resigned_acceptance  (-0.35, -0.35)  low energy / unpleasant   #98a8c0
    sinking_despair      (-0.50, -0.50)  low energy / unpleasant   #98a8c0
    deep_despair         (-0.65, -0.65)  low energy / unpleasant   #98a8c0
    relaxed_contentment  ( 0.50, -0.50)  low energy / pleasant     #a0a888
    neutral              central band    -- not a quadrant --      #909090

Three categories therefore share ``#98a8c0`` and two share ``#e0c080``.
That is deliberate: the shared colour encodes the quadrant, and the
category is identified by its axis label. It is also exactly why the
chart is a *bar* chart rather than a pie — a pie would make the repeated
colours unreadable, whereas on a labelled axis they group the bars
usefully. For the same "don't create ambiguity" reason the bars carry
raw counts rather than percentages, which keeps any ``{d}%`` formatter
string out of the options dict (see the last test in this file).

Each test imports the function it needs inside its own body, matching
``tests/test_history.py``'s helper pattern: a missing symbol then fails
these tests individually instead of collapsing the whole module into one
collection error.
"""

from typing import Any, Callable

import pytest

# FE-2's four palette entries, as configured by frontend.configure_theme().
HIGH_ENERGY_UNPLEASANT = "#783020"
HIGH_ENERGY_PLEASANT = "#e0c080"
LOW_ENERGY_UNPLEASANT = "#98a8c0"
LOW_ENERGY_PLEASANT = "#a0a888"

# `neutral` is a central band rather than a quadrant, so it has no palette
# entry to claim; a plain grey literal is the honest encoding. Same
# rationale as FE-4's caption fills, which are plain hex because they are
# contrast *against* the palette rather than part of it.
NEUTRAL_GREY = "#909090"

# MC-1's category identifiers, in MC-1's anchor-table order with the
# non-anchored `neutral` band last. This is the order the eight bars are
# rendered in.
EXPECTED_ORDER = (
    "reckless_energy",
    "energetic_optimism",
    "peak_excitement",
    "resigned_acceptance",
    "sinking_despair",
    "deep_despair",
    "relaxed_contentment",
    "neutral",
)

CATEGORY_COLOURS = {
    "reckless_energy": HIGH_ENERGY_UNPLEASANT,
    "energetic_optimism": HIGH_ENERGY_PLEASANT,
    "peak_excitement": HIGH_ENERGY_PLEASANT,
    "resigned_acceptance": LOW_ENERGY_UNPLEASANT,
    "sinking_despair": LOW_ENERGY_UNPLEASANT,
    "deep_despair": LOW_ENERGY_UNPLEASANT,
    "relaxed_contentment": LOW_ENERGY_PLEASANT,
    "neutral": NEUTRAL_GREY,
}

EXPECTED_AXIS_LABELS = [
    "Reckless Energy",
    "Energetic Optimism",
    "Peak Excitement",
    "Resigned Acceptance",
    "Sinking Despair",
    "Deep Despair",
    "Relaxed Contentment",
    "Neutral",
]

# A partial payload: three categories present, five absent. Real responses
# always carry all eight, but the function must not depend on that -- an
# absent key is what the "renders as zero" test below pins.
PARTIAL_DISTRIBUTION = {
    "energetic_optimism": {"count": 5, "percentage": 50.0},
    "deep_despair": {"count": 3, "percentage": 30.0},
    "neutral": {"count": 2, "percentage": 20.0},
}


def _category_colour() -> Callable[[str], str]:
    """Return ``frontend.analytics.category_colour``."""
    from frontend.analytics import category_colour

    return category_colour


def _category_order() -> tuple[str, ...]:
    """Return ``frontend.analytics.CATEGORY_ORDER``."""
    from frontend.analytics import CATEGORY_ORDER

    return CATEGORY_ORDER


def _distribution_options() -> Callable[[dict], dict]:
    """Return ``frontend.analytics.distribution_options``."""
    from frontend.analytics import distribution_options

    return distribution_options


def _quadrant_colours() -> dict[str, str]:
    """Return ``frontend.QUADRANT_COLOURS``."""
    from frontend import QUADRANT_COLOURS

    return QUADRANT_COLOURS


def _bars(distribution: dict) -> list[dict]:
    """The single bar series' data list, for a given distribution payload."""
    return _distribution_options()(distribution)["series"][0]["data"]


def _strings(value: Any) -> list[str]:
    """Every string appearing anywhere inside a nested options structure."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for item in value.items() for part in item for s in _strings(part)]
    if isinstance(value, (list, tuple)):
        return [s for part in value for s in _strings(part)]
    return []


# --- the colour mapping ------------------------------------------------------


@pytest.mark.parametrize(
    ("category", "colour"), sorted(CATEGORY_COLOURS.items()), ids=sorted(CATEGORY_COLOURS)
)
def test_each_category_takes_its_anchor_quadrants_colour(category: str, colour: str) -> None:
    """Each of MC-1's eight categories maps to the FE-2 colour of its anchor's quadrant.

    Shared colours are intended, not a bug: the three low-energy/unpleasant
    categories all answer #98a8c0 and the two high-energy/pleasant ones both
    answer #e0c080, because the colour encodes the quadrant and the axis
    label encodes the category.
    """
    assert _category_colour()(category) == colour


def test_an_unrecognised_category_falls_back_to_the_neutral_grey() -> None:
    """An unknown category name answers the neutral grey rather than raising.

    If the backend classifier ever grows a ninth category, the analytics
    page degrades to a grey bar instead of failing to render at all.
    """
    assert _category_colour()("some_future_category") == NEUTRAL_GREY


def test_quadrant_colours_carries_fe2s_four_palette_entries() -> None:
    """FE-2's four hexes live in one named constant, which the theme and this page share.

    FE-9a moves them out of the ``app.colors()`` call so ``category_colour``
    can reference them by name rather than re-typing the literals. The four
    ``test_brand_palette_defines_*`` tests in tests/test_frontend.py pin the
    other end of that: ``configure_theme()`` must still bind exactly these.
    """
    assert _quadrant_colours() == {
        "high_energy_unpleasant": HIGH_ENERGY_UNPLEASANT,
        "high_energy_pleasant": HIGH_ENERGY_PLEASANT,
        "low_energy_unpleasant": LOW_ENERGY_UNPLEASANT,
        "low_energy_pleasant": LOW_ENERGY_PLEASANT,
    }


# --- the category ordering ---------------------------------------------------


def test_category_order_lists_the_eight_categories_with_neutral_last() -> None:
    """The bar order is fixed here, not inherited from the API's key order.

    ``calculate_quadrant_distribution`` happens to emit its keys in this
    order today, but the chart must not depend on a backend dict's
    iteration order for its x-axis.
    """
    assert tuple(_category_order()) == EXPECTED_ORDER


# --- the distribution chart's options ----------------------------------------


def test_distribution_options_renders_one_bar_per_category() -> None:
    """All eight categories get a bar, including the five absent from the payload."""
    assert len(_bars(PARTIAL_DISTRIBUTION)) == len(EXPECTED_ORDER)


def test_distribution_options_labels_the_axis_in_title_case() -> None:
    """The x-axis names the eight categories in Title Case, in CATEGORY_ORDER."""
    options = _distribution_options()(PARTIAL_DISTRIBUTION)

    assert options["xAxis"]["data"] == EXPECTED_AXIS_LABELS


def test_distribution_options_takes_each_bars_height_from_the_payload_count() -> None:
    """A bar's value is its category's ``count``, not its ``percentage``.

    Counts keep the y-axis unit-free and keep a "{d}%" formatter string out
    of the options dict entirely -- see the brace test at the end of this
    file for why that matters.
    """
    bars = _bars(PARTIAL_DISTRIBUTION)
    heights = dict(zip(EXPECTED_ORDER, [bar["value"] for bar in bars]))

    assert heights["energetic_optimism"] == 5
    assert heights["deep_despair"] == 3
    assert heights["neutral"] == 2


def test_distribution_options_renders_an_absent_category_as_zero() -> None:
    """A category missing from the payload gets a zero-height bar, not a KeyError."""
    bars = _bars(PARTIAL_DISTRIBUTION)
    heights = dict(zip(EXPECTED_ORDER, [bar["value"] for bar in bars]))

    assert heights["peak_excitement"] == 0
    assert heights["relaxed_contentment"] == 0


def test_distribution_options_colours_each_bar_by_its_category() -> None:
    """Every bar carries its category's quadrant colour on its own itemStyle."""
    bars = _bars(PARTIAL_DISTRIBUTION)
    colours = [bar["itemStyle"]["color"] for bar in bars]

    assert colours == [CATEGORY_COLOURS[category] for category in EXPECTED_ORDER]


def test_distribution_options_uses_a_bar_series_rather_than_a_pie() -> None:
    """Exactly one series, of type "bar".

    Pinned rather than left to taste: with three categories sharing #98a8c0
    and two sharing #e0c080, a pie chart's slices would be indistinguishable.
    A bar chart identifies each category by its axis label instead.
    """
    series = _distribution_options()(PARTIAL_DISTRIBUTION)["series"]

    assert len(series) == 1
    assert series[0]["type"] == "bar"


def test_distribution_options_carries_no_brace_in_any_string() -> None:
    """No options string contains a brace, so the rendered page stays parseable.

    tests/test_frontend.py's ``_rendered_props`` walks the served HTML
    counting { and } without string awareness. Verified empirically against
    NiceGUI 3.16.0: a balanced ECharts template ("{b}: {d}%") survives that
    walk, but an unbalanced one ("{b") raises JSONDecodeError and breaks
    props parsing for the *whole page*, taking unrelated tests with it.
    Banning braces outright is the cheap, checkable rule.
    """
    offenders = [
        s for s in _strings(_distribution_options()(PARTIAL_DISTRIBUTION)) if "{" in s or "}" in s
    ]

    assert offenders == []
