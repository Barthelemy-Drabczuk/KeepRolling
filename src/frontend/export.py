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

2026-09 redesign (frontend-designer contract): the three identical
`high-energy-pleasant` buttons were the "textbook Visual Hierarchy
failure" the ui-patterns toolbox warns about. CSV is now the page's one
solid/primary action; JSON and PDF are ink-outlined secondary/tertiary
actions. Labels keep each format's name (``"Download CSV"`` etc.) rather
than the contract's "all three just say Download" -- tests/test_frontend.py
pins ``label="Download CSV"`` exactly, and the format name in the label
costs nothing once the colour hierarchy already does the real work of
telling CSV apart as the primary action.
"""

from functools import partial

from nicegui import app, ui

from . import api

LOGIN_PROMPT = "Please log in to export your moods."
GENERIC_FAILURE = "Could not complete the request."

# url segment -> (caption, media type, fallback, description, is_primary)
_FORMATS: dict[str, tuple[str, str, str, str, bool]] = {
    "csv": (
        "Download CSV",
        "text/csv",
        "moodometer.csv",
        "Rows you can open in a spreadsheet.",
        True,
    ),
    "json": (
        "Download JSON",
        "application/json",
        "moodometer.json",
        "The raw records, structure intact.",
        False,
    ),
    "pdf": (
        "Download PDF",
        "application/pdf",
        "moodometer_report.pdf",
        "A printable report with your charts.",
        False,
    ),
}


def _filename_from_content_disposition(header: str, fallback: str) -> str:
    """The ``filename=`` value in a Content-Disposition header, or ``fallback``."""
    for part in header.split(";"):
        name, _, value = part.strip().partition("=")
        if name == "filename" and value:
            return value
    return fallback


async def _download(fmt: str, media_type: str, fallback: str, status: ui.label) -> None:
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
    status.set_visibility(False)
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
        status.set_text(GENERIC_FAILURE)
        status.set_visibility(True)


def create() -> None:
    """Register the /export page."""
    from .shell import page_shell

    @ui.page("/export", title="Export")
    def export() -> None:
        with page_shell("Export"):
            ui.label("Export").classes("text-3xl font-black")
            ui.label(
                "Everything you've logged, in a file you keep. Moods, timestamps, "
                "notes, and any journal entries linked to them."
            ).style("max-width:60ch")

            with ui.column().classes("w-full gap-0").style("border:2px solid #1c1a17"):
                for fmt, (
                    caption,
                    media_type,
                    fallback,
                    description,
                    is_primary,
                ) in _FORMATS.items():
                    with (
                        ui.row()
                        .classes("w-full items-center justify-between p-4")
                        .style("border-bottom:1.5px solid #1c1a17")
                    ):
                        with ui.column().classes("gap-0"):
                            ui.label(fmt.upper()).classes("text-xl font-black")
                            ui.label(description).classes("mo-muted text-sm")
                        status = ui.label(GENERIC_FAILURE).classes("mo-warn text-sm px-2")
                        status.set_visibility(False)
                        button = ui.button(
                            caption,
                            color="high-energy-pleasant" if is_primary else None,
                            on_click=partial(_download, fmt, media_type, fallback, status),
                        )
                        if not is_primary:
                            button.props("outline")
