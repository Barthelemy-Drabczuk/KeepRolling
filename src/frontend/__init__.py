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

from nicegui import app, ui

from . import analytics as analytics_page
from . import auth as auth_pages
from . import export, history, journal, mood_pad

QUADRANT_COLOURS: dict[str, str] = {
    "high_energy_unpleasant": "#783020",
    "high_energy_pleasant": "#e0c080",
    "low_energy_unpleasant": "#98a8c0",
    "low_energy_pleasant": "#a0a888",
}

# The 8-category mood taxonomy's colours. Four are QUADRANT_COLOURS values by
# reference (never duplicated literals), matching the pad's fixed quadrant
# fills; the other four are new tokens for the zones the meme reference image
# carves out of those quadrants. Order matches analytics.CATEGORY_ORDER.
ZONE_COLOURS: dict[str, str] = {
    "reckless_energy": QUADRANT_COLOURS["high_energy_unpleasant"],
    "energetic_optimism": QUADRANT_COLOURS["high_energy_pleasant"],
    "peak_excitement": "#ecd980",
    "resigned_acceptance": "#e8a05f",
    "sinking_despair": QUADRANT_COLOURS["low_energy_unpleasant"],
    "deep_despair": "#8494b0",
    "relaxed_contentment": QUADRANT_COLOURS["low_energy_pleasant"],
    "neutral": "#909090",
}

# The visible label everywhere is the meme caption, not the Title Case name
# category_label() renders for aria-labels/tooltips.
ZONE_CAPTIONS: dict[str, str] = {
    "reckless_energy": "Fuck it we ball",
    "energetic_optimism": "We are so fucking back",
    "peak_excitement": "Let's fucking goooo",
    "resigned_acceptance": "It is what it is",
    "sinking_despair": "It's so over",
    "deep_despair": "Mom would be sad",
    "relaxed_contentment": "We vibing",
    "neutral": "Neutral",
}

# House style tokens shared by every page: warm-grey canvas, ink text/rules,
# radius 0 throughout, Archivo for display type. See moodometer_chart.jpg --
# this is the palette the 2026-09 redesign draws its "printed instrument
# panel" language from.
INK = "#1c1a17"
CANVAS = "#e8e3d9"
SURFACE = "#f6f3ec"
MUTED = "#5d574c"
WARN = "#e8a05f"

_HOUSE_STYLE_CSS = f"""
<style>
  body {{ background: {CANVAS}; color: {INK}; font-family: 'Archivo', sans-serif; }}
  .mo-ink {{ color: {INK}; }}
  .mo-muted {{ color: {MUTED}; }}
  .mo-surface {{ background: {SURFACE}; }}
  .mo-hairline {{ border-color: {INK} !important; }}
  .mo-radius-0, .mo-radius-0 * {{ border-radius: 0 !important; }}
  .mo-warn {{ background: {WARN}; color: {INK}; }}
  .mo-tabular {{ font-variant-numeric: tabular-nums; }}
  /* shell.py's responsive nav: NiceGUI's static bundle doesn't carry
     Tailwind's responsive `md:`-prefixed utilities (only the base ones),
     and Quasar's own bundled CSS defines a literal `.hidden` class
     (`display: none !important`) that would otherwise permanently hide
     anything using it regardless of viewport -- hence these two custom,
     explicitly-media-queried classes instead of `hidden md:flex`. */
  .mo-sidebar {{ display: flex !important; }}
  .mo-bottombar {{ display: none !important; }}
  @media (max-width: 767.98px) {{
    .mo-sidebar {{ display: none !important; }}
    .mo-bottombar {{ display: flex !important; }}
  }}
</style>
"""


def configure_theme() -> None:
    """Bind the circumplex quadrant colours into Quasar's brand palette.

    Only ``app.colors()`` -- not a UI element, so it's unaffected by the
    constraint below -- lives here; it's still the only thing the pinned
    brand-palette tests read.
    """
    app.colors(**QUADRANT_COLOURS)


def inject_house_style() -> None:
    """Load the shared house-style font/reset used by every redesigned page.

    Must be called from *inside* a ``@ui.page`` function body (shell.py's
    ``page_shell`` and auth.py's login/register both do this), never from
    module-level code like ``configure_theme()`` above: ``app.py`` calls
    that before ``ui.run_with()``, and NiceGUI discards any UI element
    -- ``ui.add_head_html`` included -- created before that point, logging
    "NiceGUI elements were created outside of a page context" rather than
    raising. Purely presentational; nothing here is read by any test.
    """
    ui.add_head_html(
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;600;900'
        '&display=swap" rel="stylesheet">'
    )
    ui.add_head_html(_HOUSE_STYLE_CSS)


def create_pages() -> None:
    """Register every NiceGUI page."""
    mood_pad.create()
    auth_pages.create()
    history.create()
    journal.create()
    analytics_page.create()
    export.create()
