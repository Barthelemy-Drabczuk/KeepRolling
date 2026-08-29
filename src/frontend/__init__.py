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

from nicegui import app

from . import analytics as analytics_page
from . import auth as auth_pages
from . import export, history, journal, mood_pad

QUADRANT_COLOURS: dict[str, str] = {
    "high_energy_unpleasant": "#783020",
    "high_energy_pleasant": "#e0c080",
    "low_energy_unpleasant": "#98a8c0",
    "low_energy_pleasant": "#a0a888",
}


def configure_theme() -> None:
    """Bind the circumplex quadrant colours into Quasar's brand palette."""
    app.colors(**QUADRANT_COLOURS)


def create_pages() -> None:
    """Register every NiceGUI page."""
    mood_pad.create()
    auth_pages.create()
    history.create()
    journal.create()
    analytics_page.create()
    export.create()
