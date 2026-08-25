"""NiceGUI frontend for Moodometer.

Every page is registered by calling ``create_pages()`` from ``app.py`` on
each app build, not via import-time ``@ui.page`` decorators. NiceGUI's
``user`` test fixture re-executes ``app.py`` per test via ``runpy``, but
Python's module cache means an already-imported module's import-time
decorators would not re-register on a second run — calling
``create_pages()`` explicitly each time is correct under both plain
``uvicorn`` startup and repeated test execution. See ARCHITECTURE.md's
FE-1 entry.

This package is a pure HTTP client of the REST API defined in ``app.py``
— it must never import ``models``, ``database``, ``auth``, or
``analytics``.
"""

from nicegui import ui


def create_pages() -> None:
    """Register every NiceGUI page."""

    @ui.page("/", title="Moodometer")
    def index() -> None:
        ui.label("Moodometer")
