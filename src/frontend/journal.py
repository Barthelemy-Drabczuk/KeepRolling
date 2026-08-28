"""The journal entries page, at /journal.

See ARCHITECTURE.md's FE-8a entry for the read-only listing, FE-8b's for
the compose form, and FE-8c's for mood linking: why entry_list is defined
inside the page function rather than at module scope, why validation runs
before the request, why a successful save re-fetches the list instead of
prepending the POST's own response body, and why the mood select is built
empty and repopulated after the fetch rather than built once the moods are
known.
"""

from datetime import datetime

import httpx
from nicegui import app, ui

from . import api
from .history import quadrant_label

JOURNAL_EMPTY = "No journal entries yet."
LOGIN_PROMPT = "Please log in to view your journal."  # page-load 401
COMPOSE_LOGIN_PROMPT = "Please log in to write a journal entry."  # save 401
GENERIC_FAILURE = "Could not complete the request."
SAVE_SUCCESS = "Journal entry saved!"
CONTENT_INVALID = "Journal entry must be between 1 and 5000 characters."
COMPOSE_LABEL = "New journal entry"
SAVE_CAPTION = "Save entry"
MOOD_SELECT_LABEL = "Link a mood"
NO_MOOD_OPTION = "No linked mood"
CONTENT_MAX = 5000
JOURNAL_LIMIT = 10
MOOD_WINDOW = 100


def _format_timestamp(raw: str) -> str:
    """Render an EntryResponse's naive-UTC ISO timestamp as ``%Y-%m-%d %H:%M UTC``."""
    return datetime.fromisoformat(raw).strftime("%Y-%m-%d %H:%M UTC")


def mood_option_label(mood: dict) -> str:
    """Caption one mood in the "Link a mood" select: timestamp, em dash, quadrant."""
    return (
        f"{_format_timestamp(mood['timestamp'])} — "
        f"{quadrant_label(mood['energy'], mood['valence'])}"
    )


def mood_line(mood: dict | None) -> str:
    """Render an entry's linked mood as one card line; "" when nothing is linked."""
    if mood is None:
        return ""
    energy = mood["energy"]
    valence = mood["valence"]
    return (
        f"Mood: {quadrant_label(energy, valence)} (Energy: {energy:.2f} · Valence: {valence:.2f})"
    )


def _mood_options(moods: dict[int, dict]) -> dict:
    """Build the select's ``{value: caption}`` map, with the ``None`` option first."""
    options: dict = {None: NO_MOOD_OPTION}
    options.update({mood_id: mood_option_label(mood) for mood_id, mood in moods.items()})
    return options


async def _fetch_entries(username: str, token: str) -> httpx.Response:
    """GET the newest ``JOURNAL_LIMIT`` journal entries for ``username``."""
    async with api.client() as http:
        return await http.get(
            f"/users/{username}/entries",
            params={"limit": JOURNAL_LIMIT},
            headers=api.auth_headers(token),
        )


async def _fetch_moods(username: str, token: str) -> httpx.Response:
    """GET the newest ``MOOD_WINDOW`` moods for ``username``, for linking and display."""
    async with api.client() as http:
        return await http.get(
            f"/users/{username}/moods",
            params={"limit": MOOD_WINDOW},
            headers=api.auth_headers(token),
        )


def create() -> None:
    """Register the /journal page."""

    @ui.page("/journal", title="Journal")
    async def journal() -> None:
        @ui.refreshable
        def entry_list(entries: list[dict], moods: dict[int, dict]) -> None:
            if entries:
                with ui.column():
                    for entry in entries:
                        with ui.card():
                            ui.label(_format_timestamp(entry["timestamp"]))
                            ui.label(entry["content"])
                            line = mood_line(moods.get(entry.get("mood_id")))
                            if line:
                                ui.label(line)
            else:
                ui.label(JOURNAL_EMPTY)

        async def save_entry() -> None:
            content = (compose.value or "").strip()
            if not content or len(content) > CONTENT_MAX:
                ui.notify(CONTENT_INVALID)
                return
            username = app.storage.user.get("username")
            token = app.storage.user.get("token")
            if not username or not token:
                ui.notify(COMPOSE_LOGIN_PROMPT)
                ui.navigate.to("/login")
                return
            payload: dict = {"content": content}
            if mood_select.value is not None:
                payload["mood_id"] = mood_select.value
            async with api.client() as http:
                response = await http.post(
                    f"/users/{username}/entries",
                    json=payload,
                    headers=api.auth_headers(token),
                )
            if response.status_code == 201:
                ui.notify(SAVE_SUCCESS)
                compose.value = ""
                mood_select.value = None
                refreshed = await _fetch_entries(username, token)
                if refreshed.status_code == 200:
                    entry_list.refresh(refreshed.json(), moods)
            elif response.status_code == 401:
                ui.notify(COMPOSE_LOGIN_PROMPT)
                ui.navigate.to("/login")
            else:
                ui.notify(GENERIC_FAILURE)

        compose = ui.textarea(label=COMPOSE_LABEL)
        compose.props(f"maxlength={CONTENT_MAX}")
        mood_select = ui.select(_mood_options({}), label=MOOD_SELECT_LABEL, value=None)
        ui.button(SAVE_CAPTION, color="high-energy-pleasant", on_click=save_entry)

        moods: dict[int, dict] = {}
        username = app.storage.user.get("username")
        token = app.storage.user.get("token")
        if not username or not token:
            entry_list([], moods)
            return

        response = await _fetch_entries(username, token)
        if response.status_code == 200:
            mood_response = await _fetch_moods(username, token)
            if mood_response.status_code == 200:
                moods = {mood["id"]: mood for mood in mood_response.json()}
                mood_select.set_options(_mood_options(moods))
            entry_list(response.json(), moods)
        elif response.status_code == 401:
            ui.label(LOGIN_PROMPT)
            ui.navigate.to("/login")
        else:
            ui.label(GENERIC_FAILURE)
