"""Shared page chrome for the 2026-09 redesign: the nav shell and zone_chip.

``page_shell(active)`` replaces the ad-hoc ``ui.link`` row that used to sit at
the bottom of ``mood_pad.py`` (and was otherwise absent from every other
page) with one consistent sidebar/bottom-bar nav, present on every route
except ``/login`` and ``/register`` (the frontend-designer contract's shell
pattern). ``zone_chip`` is the "colour swatch + full caption, never colour
alone" component reused by the history table, the journal feed and mood
select, and the analytics stat strip.

Both import ``ZONE_COLOURS``/``ZONE_CAPTIONS`` lazily, inside the function
body rather than at module scope: ``frontend/__init__.py`` imports its page
submodules (which import this module) before it defines those two dicts, the
same ordering constraint ``analytics.category_colour`` already documents for
``QUADRANT_COLOURS``.
"""

from contextlib import contextmanager
from typing import Iterator, Literal

from nicegui import ui

_NAV_ITEMS: tuple[tuple[str, str], ...] = (
    ("Log", "/"),
    ("History", "/history"),
    ("Journal", "/journal"),
    ("Analytics", "/analytics"),
    ("Export", "/export"),
)


@contextmanager
def page_shell(active: str) -> Iterator[None]:
    """Wrap a page's body in the shared sidebar/bottom-bar nav.

    ``active`` names the current page ("Log", "History", "Journal",
    "Analytics" or "Export") so its nav item renders in the selected state.
    Not used by ``/login``/``/register``, which render full-bleed with no
    shell per the contract (they call ``inject_house_style()`` directly).
    """
    from . import inject_house_style

    inject_house_style()
    with ui.row().classes("w-full items-stretch no-wrap").style("min-height:100vh;margin:0"):
        with (
            ui.column()
            .classes("mo-sidebar justify-between mo-surface")
            .style("width:220px;padding:16px;border-right:2px solid #1c1a17;min-height:100vh")
        ):
            with ui.column().classes("gap-1"):
                ui.label("MOODOMETER").classes("text-xl font-black leading-tight")
                for label, href in _NAV_ITEMS:
                    is_active = label == active
                    link = (
                        ui.link(label, href)
                        .classes("no-underline block")
                        .style(
                            "padding:8px 12px;"
                            + (
                                "background:#1c1a17;color:#e8e3d9;font-weight:700;"
                                if is_active
                                else "color:#1c1a17;"
                            )
                        )
                    )
                    if is_active:
                        link.props('aria-current="page"')
            ui.label().classes("mo-muted text-xs")

        with ui.column().classes("flex-grow gap-6").style("padding:24px;padding-bottom:72px"):
            yield

        with (
            ui.row()
            .classes("mo-bottombar justify-around mo-surface")
            .style(
                "position:fixed;bottom:0;left:0;right:0;border-top:2px solid #1c1a17;z-index:1000"
            )
        ):
            for label, href in _NAV_ITEMS:
                ui.link(label, href).classes("no-underline text-center").style(
                    "font-size:12px;padding:12px 8px;"
                    + ("font-weight:900;color:#1c1a17;" if label == active else "color:#5d574c;")
                )


def zone_chip(category: str, size: Literal["sm", "md", "lg"] = "sm") -> ui.row:
    """A colour swatch plus its full caption -- colour is never the only signal.

    Used in history rows, the journal feed/mood select, and the analytics
    stat strip. ``size`` controls the swatch's pixel dimensions and the
    caption's text size; callers may still ``.classes()``/``.style()`` the
    returned row further (mood_pad.py's live readout block does).
    """
    from . import ZONE_CAPTIONS, ZONE_COLOURS

    swatch_px = {"sm": 14, "md": 18, "lg": 28}[size]
    text_class = {"sm": "text-sm", "md": "text-base", "lg": "text-2xl font-black"}[size]
    colour = ZONE_COLOURS.get(category, "#909090")
    caption = ZONE_CAPTIONS.get(category, category.replace("_", " ").title())

    row = ui.row().classes("items-center gap-2")
    with row:
        ui.element("div").style(
            f"width:{swatch_px}px;height:{swatch_px}px;background:{colour};"
            f"border:1.5px solid #1c1a17;flex-shrink:0"
        )
        ui.label(caption).classes(text_class).props(f'title="{category.replace("_", " ").title()}"')
    return row
