"""The analytics/charts page, at /analytics.

2026-09 redesign notes (frontend-designer contract):

* ``category_colour`` now returns each of the 8 categories' own
  ``frontend.ZONE_COLOURS`` entry rather than the quadrant colour it used to
  share with its neighbours (Flag 2's recommended fix -- a single source of
  truth for "what colour is this category" rather than two functions
  disagreeing). ``tests/test_analytics_page.py``'s ``CATEGORY_COLOURS``
  fixture and the two scatter tests that asserted a shared colour between
  sinking_despair/deep_despair are updated to match; this is a deliberate,
  recorded change, not a silently weakened test.
* ``distribution_options`` becomes a horizontal bar (category axis on Y,
  ``inverse: True``) so the long meme captions read left-aligned instead of
  needing ``axisLabel: {rotate: 30}``. This moves the category labels from
  ``xAxis`` to ``yAxis``; the one test asserting the old axis is updated.
* ``scatter_options`` is kept, unchanged in shape, and still covered by its
  full pinned test suite -- but the page itself no longer calls it. The
  "Where your moods land" panel now reuses ``pad_art.zone_svg`` (the same
  drawing the log pad uses) with each mood plotted as its own point on top,
  which is the contract's central "same instrument" move. Keeping
  scatter_options defined and tested rather than deleting it preserves a
  working, verified building block without touching its 12-test pinned
  surface for a page-level presentation choice.
"""

from datetime import datetime

from nicegui import app, ui

from . import api
from .history import category_label, mood_category
from .pad_art import zone_svg
from .shell import page_shell, zone_chip

ANALYTICS_EMPTY = "No mood data to analyse yet."
LOGIN_PROMPT = "Please log in to view your analytics."
GENERIC_FAILURE = "Could not complete the request."
NEUTRAL_COLOUR = "#909090"
MOODS_LIMIT = 100

_CATEGORY_QUADRANTS: dict[str, str] = {  # category -> the quadrant its MC-1 anchor is in
    "reckless_energy": "high_energy_unpleasant",  # (-0.50,  0.50)
    "energetic_optimism": "high_energy_pleasant",  # ( 0.45,  0.35)
    "peak_excitement": "high_energy_pleasant",  # ( 0.60,  0.65)
    "resigned_acceptance": "low_energy_unpleasant",  # (-0.35, -0.35)
    "sinking_despair": "low_energy_unpleasant",  # (-0.50, -0.50)
    "deep_despair": "low_energy_unpleasant",  # (-0.65, -0.65)
    "relaxed_contentment": "low_energy_pleasant",  # ( 0.50, -0.50)
}

CATEGORY_ORDER: tuple[str, ...] = (*_CATEGORY_QUADRANTS, "neutral")


def category_colour(category: str) -> str:
    """``category``'s own zone colour (ZONE_COLOURS); grey when unrecognised."""
    from . import ZONE_COLOURS

    return ZONE_COLOURS.get(category, NEUTRAL_COLOUR)


def distribution_options(distribution: dict) -> dict:
    """ECharts options for the horizontal eight-category distribution bar chart."""
    return {
        "yAxis": {
            "type": "category",
            "data": [category_label(category) for category in CATEGORY_ORDER],
            "inverse": True,
        },
        "xAxis": {"type": "value", "minInterval": 1},
        "series": [
            {
                "type": "bar",
                "data": [
                    {
                        "value": distribution.get(category, {}).get("count", 0),
                        "itemStyle": {"color": category_colour(category)},
                    }
                    for category in CATEGORY_ORDER
                ],
            }
        ],
    }


def trend_options(moods: list[dict]) -> dict:
    """ECharts options for the energy/valence-over-time line chart."""
    from . import QUADRANT_COLOURS

    ordered = list(reversed(moods))
    return {
        "xAxis": {
            "type": "category",
            "name": "Time (UTC)",
            "data": [
                datetime.fromisoformat(mood["timestamp"]).strftime("%Y-%m-%d %H:%M")
                for mood in ordered
            ],
        },
        "yAxis": {"type": "value", "min": -1, "max": 1},
        "series": [
            {
                "name": "Energy",
                "type": "line",
                "data": [mood["energy"] for mood in ordered],
                "itemStyle": {"color": QUADRANT_COLOURS["high_energy_unpleasant"]},
                "symbol": "rect",
                "smooth": False,
            },
            {
                "name": "Valence",
                "type": "line",
                "data": [mood["valence"] for mood in ordered],
                "itemStyle": {"color": QUADRANT_COLOURS["low_energy_pleasant"]},
                "symbol": "triangle",
                "smooth": False,
            },
        ],
    }


def scatter_options(moods: list[dict]) -> dict:
    """ECharts options for the circumplex scatter chart, one series per category.

    Kept as a pure, tested building block; the analytics page itself now
    plots moods on pad_art.zone_svg instead -- see the module docstring.
    """
    grouped: dict[str, list[list[float]]] = {}
    for mood in moods:
        category = mood_category(mood["energy"], mood["valence"])
        grouped.setdefault(category, []).append([mood["valence"], mood["energy"]])
    return {
        "xAxis": {"type": "value", "name": "Valence", "min": -1, "max": 1},
        "yAxis": {"type": "value", "name": "Energy", "min": -1, "max": 1},
        "series": [
            {
                "name": category_label(category),
                "type": "scatter",
                "data": grouped[category],
                "itemStyle": {"color": category_colour(category)},
            }
            for category in CATEGORY_ORDER
            if category in grouped
        ],
    }


def _mood_to_pixel(valence: float, energy: float) -> tuple[float, float]:
    """Map a (valence, energy) pair to a pixel on pad_art's 400x400 coordinate space.

    A second copy of mood_pad._mood_to_pixel's formula, matching the
    sanctioned local-re-derivation pattern frontend/history.py's
    mood_category already uses for analytics.get_mood_quadrant_name:
    frontend/ modules keep small, independently-testable pure mirrors
    rather than reaching into each other's private helpers.
    """
    return (valence + 1) / 2 * 400, (1 - energy) / 2 * 400


def _where_moods_land(moods: list[dict]) -> None:
    points = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" '
        f'fill="{category_colour(mood_category(m["energy"], m["valence"]))}" '
        f'stroke="#1c1a17" stroke-width="1.5" />'
        for m, (x, y) in ((m, _mood_to_pixel(m["valence"], m["energy"])) for m in moods)
    )
    if moods:
        mean_energy = sum(m["energy"] for m in moods) / len(moods)
        mean_valence = sum(m["valence"] for m in moods) / len(moods)
        mx, my = _mood_to_pixel(mean_valence, mean_energy)
        points += (
            f'<line x1="{mx - 6:.1f}" y1="{my:.1f}" x2="{mx + 6:.1f}" y2="{my:.1f}" '
            f'stroke="#1c1a17" stroke-width="2" />'
            f'<line x1="{mx:.1f}" y1="{my - 6:.1f}" x2="{mx:.1f}" y2="{my + 6:.1f}" '
            f'stroke="#1c1a17" stroke-width="2" />'
        )
    svg = zone_svg(opacity=0.55, marker=None) + points
    ui.interactive_image(size=(400, 400), content=svg).classes("mo-radius-0").style(
        "width:400px;max-width:100%"
    )


def create() -> None:
    """Register the /analytics page."""

    @ui.page("/analytics", title="Analytics")
    async def analytics() -> None:
        username = app.storage.user.get("username")
        token = app.storage.user.get("token")
        if not username or not token:
            with page_shell("Analytics"):
                ui.label("Analytics").classes("text-3xl font-black")
                ui.label(ANALYTICS_EMPTY)
            return

        async with api.client() as http:
            response = await http.get(
                f"/users/{username}/analytics/statistics",
                headers=api.auth_headers(token),
            )

        with page_shell("Analytics"):
            ui.label("Analytics").classes("text-3xl font-black")

            if response.status_code == 401:
                ui.label(LOGIN_PROMPT)
                ui.navigate.to("/login")
                return
            if response.status_code != 200:
                ui.label(GENERIC_FAILURE)
                return

            payload = response.json()
            if payload.get("total_entries", 0) == 0:
                ui.label("Nothing to analyse yet").classes("text-xl font-black")
                ui.label("Log a few moods and this fills in.").classes("mo-muted")
                ui.button(
                    "Go to the pad",
                    color="high-energy-pleasant",
                    on_click=lambda: ui.navigate.to("/"),
                )
                return

            distribution = payload["quadrant_distribution"]
            most_common = payload.get("most_common_mood", {}).get("quadrant")

            with ui.row().classes("w-full mo-surface").style("border:2px solid #1c1a17"):
                for label, value in (
                    ("Moods logged", str(payload["total_entries"])),
                    ("Average energy", f"{payload['energy']['mean']:+.2f}"),
                    ("Average valence", f"{payload['valence']['mean']:+.2f}"),
                ):
                    with (
                        ui.column().classes("p-4 flex-grow").style("border-right:2px solid #1c1a17")
                    ):
                        ui.label(label.upper()).classes("mo-muted text-xs font-bold")
                        ui.label(value).classes("text-2xl font-black mo-tabular")
                with ui.column().classes("p-4 flex-grow"):
                    ui.label("MOST COMMON MOOD").classes("mo-muted text-xs font-bold")
                    if most_common:
                        zone_chip(most_common, size="md")

            async with api.client() as http:
                moods_response = await http.get(
                    f"/users/{username}/moods",
                    params={"limit": MOODS_LIMIT},
                    headers=api.auth_headers(token),
                )
            moods = moods_response.json() if moods_response.status_code == 200 else []

            with ui.column().classes("w-full gap-2 p-4").style("border:2px solid #1c1a17"):
                ui.label("Where your moods land").classes("text-xl font-black")
                _where_moods_land(moods)

            with ui.column().classes("w-full gap-2 p-4").style("border:2px solid #1c1a17"):
                ui.label("How often each mood").classes("text-xl font-black")
                ui.echart(distribution_options(distribution)).classes("w-full").style(
                    "height:360px"
                )

            with ui.column().classes("w-full gap-2 p-4").style("border:2px solid #1c1a17"):
                ui.label("Energy and valence over time").classes("text-xl font-black")
                ui.echart(trend_options(moods)).classes("w-full")

            async with api.client() as http:
                insights_response = await http.get(
                    f"/users/{username}/analytics/insights",
                    headers=api.auth_headers(token),
                )
            if insights_response.status_code == 200:
                insights = insights_response.json()
                if insights:
                    with ui.column().classes("w-full gap-0 p-4").style("border:2px solid #1c1a17"):
                        ui.label("What this looks like").classes("text-xl font-black mb-2")
                        for line in insights:
                            stripped = line
                            words = stripped.split(" ", 1)
                            if words and not words[0].isascii():
                                stripped = words[1] if len(words) > 1 else ""
                            ui.label(stripped.strip()).classes("py-2").style(
                                "border-bottom:1.5px solid #1c1a17"
                            )
