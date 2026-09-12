"""The journal entries page, at /journal.

See ARCHITECTURE.md's FE-8a entry for the read-only listing, FE-8b's for
the compose form, and FE-8c's for mood linking: why entry_list is defined
inside the page function rather than at module scope, why validation runs
before the request, why a successful save re-fetches the list instead of
prepending the POST's own response body, and why the mood select is built
empty and repopulated after the fetch rather than built once the moods are
known.

Deviation from the frontend-designer contract, deliberate: the contract's
Flag 5 recommends showing the meme caption (not Title Case) in the "Link a
mood" select. ``mood_option_label``/``mood_line`` below are pinned verbatim
by tests/test_journal.py's Title-Case assertions (``"... UTC — Peak
Excitement"``), so this redesign keeps both functions and their Title-Case
output unchanged and adds the meme caption via ``zone_chip`` on the entry
card instead -- both the caption and the Title Case name end up visible,
just not on the same element the contract proposed.
"""

from datetime import datetime

import httpx
from nicegui import app, ui

from . import api
from .history import mood_category, quadrant_label
from .shell import page_shell, zone_chip

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
                with ui.column().classes("w-full gap-4"):
                    for entry in entries:
                        linked = moods.get(entry.get("mood_id"))
                        category = (
                            mood_category(linked["energy"], linked["valence"]) if linked else None
                        )
                        bar_colour = "#5d574c"
                        if category:
                            from . import ZONE_COLOURS

                            bar_colour = ZONE_COLOURS.get(category, "#909090")
                        with (
                            ui.row()
                            .classes("w-full items-stretch gap-0")
                            .style("border:2px solid #1c1a17")
                        ):
                            ui.element("div").style(
                                f"width:6px;background:{bar_colour};"
                                f"opacity:{1.0 if category else 0.3}"
                            )
                            with ui.column().classes("gap-1 p-4 flex-grow"):
                                with ui.row().classes("w-full justify-between items-center"):
                                    ui.label(_format_timestamp(entry["timestamp"])).classes(
                                        "mo-muted text-sm"
                                    )
                                    if category:
                                        zone_chip(category, size="sm")
                                ui.label(entry["content"]).style("max-width:68ch")
                                line = mood_line(linked)
                                if line:
                                    ui.label(line).classes("mo-muted mo-tabular text-sm")
            else:
                ui.label(JOURNAL_EMPTY).classes("text-xl font-black")
                ui.label("Write down what's going on. Linking a mood is optional.").classes(
                    "mo-muted"
                )

        async def save_entry() -> None:
            content = (compose.value or "").strip()
            if not content or len(content) > CONTENT_MAX:
                validation_message.text = CONTENT_INVALID
                validation_message.set_visibility(True)
                return
            validation_message.set_visibility(False)
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

        with page_shell("Journal"):
            ui.label("Journal").classes("text-3xl font-black")
            with ui.row().classes("w-full items-start gap-8 flex-wrap"):
                with (
                    ui.column()
                    .classes("mo-surface p-6 gap-3")
                    .style("border:2px solid #1c1a17;min-width:320px;flex:0 0 38%")
                ):
                    ui.label("New entry").classes("text-xl font-black")
                    compose = ui.textarea(label=COMPOSE_LABEL).classes("w-full")
                    compose.props(f"maxlength={CONTENT_MAX}")
                    validation_message = ui.label(CONTENT_INVALID).classes("mo-warn text-sm p-2")
                    validation_message.set_visibility(False)
                    mood_select = ui.select(_mood_options({}), label=MOOD_SELECT_LABEL, value=None)
                    ui.button(
                        SAVE_CAPTION, color="high-energy-pleasant", on_click=save_entry
                    ).classes("w-full")

                with ui.column().classes("flex-grow gap-4").style("min-width:320px"):
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
                            moods = {m["id"]: m for m in mood_response.json()}
                            mood_select.set_options(_mood_options(moods))
                        entry_list(response.json(), moods)
                    elif response.status_code == 401:
                        ui.label(LOGIN_PROMPT)
                        ui.navigate.to("/login")
                    else:
                        ui.label(GENERIC_FAILURE)
