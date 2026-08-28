"""The mood history page, at /history.

See ARCHITECTURE.md's FE-7 entry for why app.storage.user must be read
before the first await, why the failure branches use inline ui.label
rather than ui.notify, and why this is the second authenticated call
site, not the third that would trigger extracting an api.auth_headers()
helper. See ARCHITECTURE.md's MC-2 entry for quadrant_label's current
contract: it mirrors analytics.get_mood_quadrant_name's 8-category
nearest-anchor logic (its <, not <=, neutral-band boundary included),
Title Cased.
"""

from datetime import datetime

from nicegui import app, ui

from . import api

EMPTY_PROMPT = "No mood entries yet. Click on the mood board to record your first mood!"
LOGIN_PROMPT = "Please log in to view your mood history."
GENERIC_FAILURE = "Could not complete the request."
HISTORY_LIMIT = 10

_COLUMNS = [
    {"name": "timestamp", "label": "Timestamp", "field": "timestamp", "align": "left"},
    {"name": "energy", "label": "Energy", "field": "energy", "align": "left"},
    {"name": "valence", "label": "Valence", "field": "valence", "align": "left"},
    {"name": "quadrant", "label": "Quadrant", "field": "quadrant", "align": "left"},
    {"name": "notes", "label": "Notes", "field": "notes", "align": "left"},
]


_CAPTION_ANCHORS: dict[str, tuple[float, float]] = {  # (valence, energy)
    "reckless_energy": (-0.50, 0.50),
    "energetic_optimism": (0.45, 0.35),
    "peak_excitement": (0.60, 0.65),
    "resigned_acceptance": (-0.35, -0.35),
    "sinking_despair": (-0.50, -0.50),
    "deep_despair": (-0.65, -0.65),
    "relaxed_contentment": (0.50, -0.50),
}


def mood_category(energy: float, valence: float) -> str:
    """Name the mood category an ``(energy, valence)`` pair falls in."""
    if abs(energy) < 0.1 and abs(valence) < 0.1:
        return "neutral"
    return min(
        _CAPTION_ANCHORS,
        key=lambda name: (
            (valence - _CAPTION_ANCHORS[name][0]) ** 2 + (energy - _CAPTION_ANCHORS[name][1]) ** 2
        ),
    )


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
    """Turn one MoodResponse JSON object into one ui.table row."""
    energy = mood["energy"]
    valence = mood["valence"]
    return {
        "id": mood["id"],
        "timestamp": _format_timestamp(mood["timestamp"]),
        "energy": f"{energy:.2f}",
        "valence": f"{valence:.2f}",
        "quadrant": quadrant_label(energy, valence),
        "notes": mood.get("notes") or "",
    }


def create() -> None:
    """Register the /history page."""

    @ui.page("/history", title="Mood history")
    async def history() -> None:
        username = app.storage.user.get("username")
        token = app.storage.user.get("token")
        if not username or not token:
            ui.label(EMPTY_PROMPT)
            return

        async with api.client() as http:
            response = await http.get(
                f"/users/{username}/moods",
                params={"limit": HISTORY_LIMIT},
                headers={"Authorization": f"Bearer {token}"},
            )

        if response.status_code == 200:
            moods = response.json()
            if moods:
                ui.table(columns=_COLUMNS, rows=[_history_row(m) for m in moods], row_key="id")
            else:
                ui.label(EMPTY_PROMPT)
        elif response.status_code == 401:
            ui.label(LOGIN_PROMPT)
            ui.navigate.to("/login")
        else:
            ui.label(GENERIC_FAILURE)
