"""The export page, at /export.

See ARCHITECTURE.md's FE-10 entry for the full contract: why the page has
no auth guard and no page-load fetch, why the three formats are a data
table plus one parametrised handler rather than a Strategy hierarchy, why
`_filename_from_content_disposition` strips each header segment (the
backend's `f"attachment; filename={filename}"` has a leading space after
the semicolon), why the response bytes are handed to `ui.download` as
`bytes` rather than a URL (bearer auth would be lost), and why `partial`
binds each button's format at construction time rather than closing over
the loop variable.
"""

from functools import partial

from nicegui import app, ui

from . import api

LOGIN_PROMPT = "Please log in to export your moods."
GENERIC_FAILURE = "Could not complete the request."

_FORMATS: dict[str, tuple[str, str, str]] = {  # url segment -> (caption, media type, fallback)
    "csv": ("Download CSV", "text/csv", "moodometer.csv"),
    "json": ("Download JSON", "application/json", "moodometer.json"),
    "pdf": ("Download PDF", "application/pdf", "moodometer_report.pdf"),
}


def _filename_from_content_disposition(header: str, fallback: str) -> str:
    """The ``filename=`` value in a Content-Disposition header, or ``fallback``."""
    for part in header.split(";"):
        name, _, value = part.strip().partition("=")
        if name == "filename" and value:
            return value
    return fallback


async def _download(fmt: str, media_type: str, fallback: str) -> None:
    """Fetch the caller's moods in ``fmt`` and hand the bytes to the browser."""
    username = app.storage.user.get("username")
    token = app.storage.user.get("token")
    if not username or not token:
        # Nothing stored: same user-visible outcome as the API's 401, but
        # short-circuited here because f"/users/{None}/export/csv" would be a
        # wrong URL and f"/users//export/csv" matches no route (Starlette's
        # {username} is [^/]+), so either would 404 into the generic branch.
        ui.notify(LOGIN_PROMPT)
        ui.navigate.to("/login")
        return
    async with api.client() as http:
        response = await http.get(
            f"/users/{username}/export/{fmt}",
            headers=api.auth_headers(token),
        )
    if response.status_code == 200:
        filename = _filename_from_content_disposition(
            response.headers.get("content-disposition", ""), fallback
        )
        ui.download(response.content, filename, media_type)
    elif response.status_code == 401:
        ui.notify(LOGIN_PROMPT)
        ui.navigate.to("/login")
    else:
        ui.notify(GENERIC_FAILURE)


def create() -> None:
    """Register the /export page."""

    @ui.page("/export", title="Export")
    def export() -> None:
        for fmt, (caption, media_type, fallback) in _FORMATS.items():
            ui.button(
                caption,
                color="high-energy-pleasant",
                on_click=partial(_download, fmt, media_type, fallback),
            )
