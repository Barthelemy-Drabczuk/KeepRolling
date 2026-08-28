"""The analytics/charts page, at /analytics."""

from datetime import datetime

from nicegui import app, ui

from . import api
from .history import category_label, mood_category

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
    """The FE-2 colour of ``category``'s anchor quadrant; grey when it has none."""
    from . import QUADRANT_COLOURS

    quadrant = _CATEGORY_QUADRANTS.get(category)
    if quadrant is None:
        return NEUTRAL_COLOUR
    return QUADRANT_COLOURS[quadrant]


def distribution_options(distribution: dict) -> dict:
    """ECharts options for the eight-bar mood-category distribution chart."""
    return {
        "xAxis": {
            "type": "category",
            "data": [category_label(category) for category in CATEGORY_ORDER],
            "axisLabel": {"interval": 0, "rotate": 30},
        },
        "yAxis": {"type": "value", "minInterval": 1},
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
            },
            {
                "name": "Valence",
                "type": "line",
                "data": [mood["valence"] for mood in ordered],
                "itemStyle": {"color": QUADRANT_COLOURS["low_energy_pleasant"]},
            },
        ],
    }


def scatter_options(moods: list[dict]) -> dict:
    """ECharts options for the circumplex scatter chart, one series per category."""
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


def create() -> None:
    """Register the /analytics page."""

    @ui.page("/analytics", title="Analytics")
    async def analytics() -> None:
        username = app.storage.user.get("username")
        token = app.storage.user.get("token")
        if not username or not token:
            ui.label(ANALYTICS_EMPTY)
            return

        async with api.client() as http:
            response = await http.get(
                f"/users/{username}/analytics/statistics",
                headers=api.auth_headers(token),
            )

        if response.status_code == 200:
            payload = response.json()
            if payload.get("total_entries", 0) > 0:
                trend_slot = ui.element("div")
                ui.echart(distribution_options(payload["quadrant_distribution"]))

                async with api.client() as http:
                    moods_response = await http.get(
                        f"/users/{username}/moods",
                        params={"limit": MOODS_LIMIT},
                        headers=api.auth_headers(token),
                    )
                if moods_response.status_code == 200:
                    moods = moods_response.json()
                    if moods:
                        with trend_slot:
                            ui.echart(trend_options(moods))
                            ui.echart(scatter_options(moods))
            else:
                ui.label(ANALYTICS_EMPTY)
        elif response.status_code == 401:
            ui.label(LOGIN_PROMPT)
            ui.navigate.to("/login")
        else:
            ui.label(GENERIC_FAILURE)
