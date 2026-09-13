"""The mood history page, at /history.

See ARCHITECTURE.md's FE-7 entry for why app.storage.user must be read
before the first await, why the failure branches use inline ui.label
rather than ui.notify, and why this is the second authenticated call
site, not the third that would trigger extracting an api.auth_headers()
helper. See ARCHITECTURE.md's MC-4 entry for quadrant_label's current
contract: it mirrors analytics.get_mood_quadrant_name's 8-category
region-membership logic (a literal hand-transcription of
frontend/pad_art.py's _ZONE_SHAPES, checked in reverse SVG-paint order
with closed intervals -- the same table analytics.py's _ZONE_RECTS
uses, kept in sync by hand across all three copies), Title Cased.

The 2026-09 redesign (frontend-designer contract) replaces the plain
ui.table with a recency strip, a client-side zone filter row, and a
zone_chip per row -- none of that is server-observable (it sits behind
the same authenticated fetch tests/test_frontend.py already documents
as manual-verification-only), so quadrant_label/mood_category/
category_label/EMPTY_PROMPT below are unchanged: they are what FE-7's
and MC-2's pinned unit tests actually exercise.
"""

from datetime import datetime

from nicegui import app, ui

from . import api
from .shell import page_shell, zone_chip

EMPTY_PROMPT = "No mood entries yet. Click on the mood board to record your first mood!"
LOGIN_PROMPT = "Please log in to view your mood history."
GENERIC_FAILURE = "Could not complete the request."
NO_FILTER_MATCHES = "No moods match these filters."
HISTORY_LIMIT = 10


# Literal transcription of src/frontend/pad_art.py's _ZONE_SHAPES, in the
# reverse of that module's SVG paint order: last painted (visually topmost)
# is tested first. A second hand-kept copy of the same table
# src/backend/app/analytics.py's _ZONE_RECTS carries -- see MC-4 in
# ARCHITECTURE.md for why a third copy is sanctioned here rather than an
# import (frontend/ must never import analytics/models/database/auth).
# (category, x_min, x_max, y_min, y_max) in the pad's 400x400 pixel space.
_ZONE_RECTS: tuple[tuple[str, int, int, int, int], ...] = (
    ("deep_despair", 0, 66, 338, 400),  # "Mom would be sad"
    ("peak_excitement", 336, 400, 0, 60),  # "Let's fucking goooo"
    ("resigned_acceptance", 0, 266, 130, 200),  # "It is what it is", upper band
    ("resigned_acceptance", 204, 266, 200, 400),  # "It is what it is", lower band
    ("relaxed_contentment", 266, 400, 200, 400),  # "We vibing"
    ("sinking_despair", 0, 204, 200, 400),  # "It's so over"
    ("reckless_energy", 0, 200, 0, 130),  # "Fuck it we ball"
)

# analytics._CATEGORY_ORDER's order, kept in sync by hand -- ZONE_COLOURS and
# frontend/analytics.py's own CATEGORY_ORDER are documented as matching it.
CATEGORY_ORDER: tuple[str, ...] = (
    "reckless_energy",
    "energetic_optimism",
    "peak_excitement",
    "resigned_acceptance",
    "sinking_despair",
    "deep_despair",
    "relaxed_contentment",
    "neutral",
)


def mood_category(energy: float, valence: float) -> str:
    """Name the mood category an ``(energy, valence)`` pair falls in."""
    if abs(energy) < 0.1 and abs(valence) < 0.1:
        return "neutral"
    x = (valence + 1) * 200
    y = (1 - energy) * 200
    for category, x_min, x_max, y_min, y_max in _ZONE_RECTS:
        if x_min <= x <= x_max and y_min <= y <= y_max:
            return category
    return "energetic_optimism"


def category_label(category: str) -> str:
    """Render a snake_case category identifier as its Title Case display label."""
    return category.replace("_", " ").title()


def quadrant_label(energy: float, valence: float) -> str:
    """Name the mood category an ``(energy, valence)`` pair falls in, Title Cased."""
    return category_label(mood_category(energy, valence))


def _format_timestamp(raw: str) -> str:
    """Render a MoodResponse's naive-UTC ISO timestamp as ``%Y-%m-%d %H:%M UTC``."""
    return datetime.fromisoformat(raw).strftime("%Y-%m-%d %H:%M UTC")


def _history_row(mood: dict) -> dict:
    """Turn one MoodResponse JSON object into one display row."""
    energy = mood["energy"]
    valence = mood["valence"]
    return {
        "id": mood["id"],
        "timestamp": _format_timestamp(mood["timestamp"]),
        "energy": f"{energy:+.2f}",
        "valence": f"{valence:+.2f}",
        "category": mood_category(energy, valence),
        "notes": mood.get("notes") or "",
    }


def _recency_strip(rows: list[dict]) -> None:
    oldest_first = list(reversed(rows))
    with ui.row().classes("items-center gap-2 w-full"):
        ui.label("Oldest").classes("mo-muted text-xs")
        with ui.row().classes("gap-0 flex-grow").style("border:2px solid #1c1a17"):
            for row in oldest_first:
                from . import ZONE_COLOURS

                colour = ZONE_COLOURS.get(row["category"], "#909090")
                block = ui.element("div").style(
                    f"background:{colour};height:36px;flex:1;border-right:1.5px solid #1c1a17"
                )
                block.props(f'title="{row["timestamp"]} — {category_label(row["category"])}"')
        ui.label("Newest").classes("mo-muted text-xs")


def _filter_row(rows: list[dict], on_change) -> dict[str, bool]:
    state = {category: True for category in CATEGORY_ORDER}

    with ui.row().classes("items-center gap-2 flex-wrap"):
        for category in CATEGORY_ORDER:
            chip = (
                zone_chip(category, size="sm")
                .classes("cursor-pointer px-2 py-1 border")
                .style("border-width:1.5px;border-color:#1c1a17")
            )

            def toggle(_, category=category, chip=chip) -> None:
                state[category] = not state[category]
                chip.style(f"opacity:{1.0 if state[category] else 0.35}")
                on_change()

            chip.on("click", toggle)
    return state


def _row_line(row: dict) -> None:
    with (
        ui.row()
        .classes("w-full items-center gap-4 py-2")
        .style("border-bottom:1.5px solid #1c1a17")
    ):
        zone_chip(row["category"], size="sm").style("width:180px")
        ui.label(row["timestamp"]).classes("mo-muted text-sm").style("width:170px")
        ui.label(row["energy"]).classes("mo-tabular text-right").style("width:70px")
        ui.label(row["valence"]).classes("mo-tabular text-right").style("width:70px")
        with ui.label(row["notes"] or "—").classes("mo-muted text-sm flex-grow"):
            if row["notes"]:
                # A tooltip element, not a raw title="..." prop: notes is
                # free user text (up to 1000 chars, MoodBase.notes) and
                # NiceGUI's tooltip handles escaping it, where an f-string
                # into a props() attribute string would not.
                ui.tooltip(row["notes"])


def create() -> None:
    """Register the /history page."""

    @ui.page("/history", title="Mood history")
    async def history() -> None:
        username = app.storage.user.get("username")
        token = app.storage.user.get("token")
        if not username or not token:
            with page_shell("History"):
                ui.label("History").classes("text-3xl font-black")
                ui.label(EMPTY_PROMPT)
            return

        async with api.client() as http:
            response = await http.get(
                f"/users/{username}/moods",
                params={"limit": HISTORY_LIMIT},
                headers=api.auth_headers(token),
            )

        with page_shell("History"):
            ui.label("History").classes("text-3xl font-black")

            if response.status_code != 200:
                if response.status_code == 401:
                    ui.label(LOGIN_PROMPT)
                    ui.navigate.to("/login")
                else:
                    ui.label(GENERIC_FAILURE)
                return

            moods = response.json()
            if not moods:
                ui.label("Nothing logged yet").classes("text-xl font-black")
                ui.label("Drop a point on the mood pad to record your first mood.").classes(
                    "mo-muted"
                )
                ui.button(
                    "Go to the pad",
                    color="high-energy-pleasant",
                    on_click=lambda: ui.navigate.to("/"),
                )
                return

            rows = [_history_row(m) for m in moods]
            _recency_strip(rows)

            @ui.refreshable
            def row_list() -> None:
                visible = [row for row in rows if filter_state[row["category"]]]
                if not visible:
                    ui.label(NO_FILTER_MATCHES).classes("mo-muted")
                    return
                with ui.column().classes("w-full gap-0").style("border-top:2px solid #1c1a17"):
                    for row in visible:
                        _row_line(row)

            filter_state = _filter_row(rows, lambda: row_list.refresh())
            row_list()
