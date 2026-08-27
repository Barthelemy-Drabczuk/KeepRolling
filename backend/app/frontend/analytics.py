"""The analytics/charts page, at /analytics."""

from nicegui import app, ui

from . import api
from .history import category_label

ANALYTICS_EMPTY = "No mood data to analyse yet."
LOGIN_PROMPT = "Please log in to view your analytics."
GENERIC_FAILURE = "Could not complete the request."
NEUTRAL_COLOUR = "#909090"

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
                headers={"Authorization": f"Bearer {token}"},
            )

        if response.status_code == 200:
            payload = response.json()
            if payload.get("total_entries", 0) > 0:
                ui.echart(distribution_options(payload["quadrant_distribution"]))
            else:
                ui.label(ANALYTICS_EMPTY)
        elif response.status_code == 401:
            ui.label(LOGIN_PROMPT)
            ui.navigate.to("/login")
        else:
            ui.label(GENERIC_FAILURE)
