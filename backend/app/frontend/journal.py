"""The journal entries page, at /journal.

See ARCHITECTURE.md's FE-8a entry for the read-only listing and FE-8b's
for the compose form: why entry_list is defined inside the page function
rather than at module scope, why validation runs before the request, and
why a successful save re-fetches the list instead of prepending the
POST's own response body.
"""

from datetime import datetime

import httpx
from nicegui import app, ui

from . import api

JOURNAL_EMPTY = "No journal entries yet."
LOGIN_PROMPT = "Please log in to view your journal."  # page-load 401
COMPOSE_LOGIN_PROMPT = "Please log in to write a journal entry."  # save 401
GENERIC_FAILURE = "Could not complete the request."
SAVE_SUCCESS = "Journal entry saved!"
CONTENT_INVALID = "Journal entry must be between 1 and 5000 characters."
COMPOSE_LABEL = "New journal entry"
SAVE_CAPTION = "Save entry"
CONTENT_MAX = 5000
JOURNAL_LIMIT = 10


def _format_timestamp(raw: str) -> str:
    """Render an EntryResponse's naive-UTC ISO timestamp as ``%Y-%m-%d %H:%M UTC``."""
    return datetime.fromisoformat(raw).strftime("%Y-%m-%d %H:%M UTC")


async def _fetch_entries(username: str, token: str) -> httpx.Response:
    """GET the newest ``JOURNAL_LIMIT`` journal entries for ``username``."""
    async with api.client() as http:
        return await http.get(
            f"/users/{username}/entries",
            params={"limit": JOURNAL_LIMIT},
            headers={"Authorization": f"Bearer {token}"},
        )


def create() -> None:
    """Register the /journal page."""

    @ui.page("/journal", title="Journal")
    async def journal() -> None:
        @ui.refreshable
        def entry_list(entries: list[dict]) -> None:
            if entries:
                with ui.column():
                    for entry in entries:
                        with ui.card():
                            ui.label(_format_timestamp(entry["timestamp"]))
                            ui.label(entry["content"])
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
            async with api.client() as http:
                response = await http.post(
                    f"/users/{username}/entries",
                    json={"content": content},
                    headers={"Authorization": f"Bearer {token}"},
                )
            if response.status_code == 201:
                ui.notify(SAVE_SUCCESS)
                compose.value = ""
                refreshed = await _fetch_entries(username, token)
                if refreshed.status_code == 200:
                    entry_list.refresh(refreshed.json())
            elif response.status_code == 401:
                ui.notify(COMPOSE_LOGIN_PROMPT)
                ui.navigate.to("/login")
            else:
                ui.notify(GENERIC_FAILURE)

        compose = ui.textarea(label=COMPOSE_LABEL)
        compose.props(f"maxlength={CONTENT_MAX}")
        ui.button(SAVE_CAPTION, color="high-energy-pleasant", on_click=save_entry)

        username = app.storage.user.get("username")
        token = app.storage.user.get("token")
        if not username or not token:
            entry_list([])
            return

        response = await _fetch_entries(username, token)
        if response.status_code == 200:
            entry_list(response.json())
        elif response.status_code == 401:
            ui.label(LOGIN_PROMPT)
            ui.navigate.to("/login")
        else:
            ui.label(GENERIC_FAILURE)
