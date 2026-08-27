"""The journal entries page, at /journal."""

from datetime import datetime

from nicegui import app, ui

from . import api

JOURNAL_EMPTY = "No journal entries yet."
LOGIN_PROMPT = "Please log in to view your journal."
GENERIC_FAILURE = "Could not complete the request."
JOURNAL_LIMIT = 10


def _format_timestamp(raw: str) -> str:
    """Render an EntryResponse's naive-UTC ISO timestamp as ``%Y-%m-%d %H:%M UTC``."""
    return datetime.fromisoformat(raw).strftime("%Y-%m-%d %H:%M UTC")


def create() -> None:
    """Register the /journal page."""

    @ui.page("/journal", title="Journal")
    async def journal() -> None:
        username = app.storage.user.get("username")
        token = app.storage.user.get("token")
        if not username or not token:
            ui.label(JOURNAL_EMPTY)
            return

        async with api.client() as http:
            response = await http.get(
                f"/users/{username}/entries",
                params={"limit": JOURNAL_LIMIT},
                headers={"Authorization": f"Bearer {token}"},
            )

        if response.status_code == 200:
            entries = response.json()
            if entries:
                with ui.column():
                    for entry in entries:
                        with ui.card():
                            ui.label(_format_timestamp(entry["timestamp"]))
                            ui.label(entry["content"])
            else:
                ui.label(JOURNAL_EMPTY)
        elif response.status_code == 401:
            ui.label(LOGIN_PROMPT)
            ui.navigate.to("/login")
        else:
            ui.label(GENERIC_FAILURE)
