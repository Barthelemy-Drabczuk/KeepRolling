"""The mood pad page, at `/`.

See ARCHITECTURE.md's FE-4 entry for the original contract: why
pixel_to_mood returns (valence, energy) -- the opposite of this
codebase's usual energy-first order, pinned by test_mood_pad.py -- and
why cross=False (avoids colliding with the mousemove already in
events). The pad's *drawing* moved to pad_art.zone_svg() in the 2026-09
redesign (see the frontend-designer contract); pixel_to_mood, nudge and
the interaction contract below are unchanged by that redesign.
"""

from nicegui import app, events, ui

from . import api
from .history import mood_category
from .pad_art import zone_svg
from .shell import page_shell

PAD_WIDTH = 400
PAD_HEIGHT = 400
QUADRANT = 200

NOTES_MAX = 1000


def pixel_to_mood(x: float, y: float, width: float, height: float) -> tuple[float, float]:
    """Map a pad pixel to a clamped ``(valence, energy)`` pair."""
    valence = min(1.0, max(-1.0, x / width * 2 - 1))
    energy = min(1.0, max(-1.0, 1 - y / height * 2))
    return valence, energy


STEP = 0.05

_NUDGES: dict[str, tuple[float, float]] = {
    "ArrowRight": (STEP, 0.0),
    "ArrowLeft": (-STEP, 0.0),
    "ArrowUp": (0.0, STEP),
    "ArrowDown": (0.0, -STEP),
}


def nudge(valence: float, energy: float, key: str) -> tuple[float, float]:
    """Move a ``(valence, energy)`` pair one step in ``key``'s direction."""
    if key not in _NUDGES:
        return valence, energy
    d_valence, d_energy = _NUDGES[key]
    return (
        round(min(1.0, max(-1.0, valence + d_valence)), 2),
        round(min(1.0, max(-1.0, energy + d_energy)), 2),
    )


def _mood_to_pixel(
    valence: float, energy: float, width: float, height: float
) -> tuple[float, float]:
    return (valence + 1) / 2 * width, (1 - energy) / 2 * height


def _readout(energy: float, valence: float) -> str:
    return f"Energy: {energy:.2f} · Valence: {valence:.2f}"


def create() -> None:
    """Register the / page."""

    @ui.page("/", title="Moodometer")
    def index() -> None:
        dragging = False
        current_valence = 0.0
        current_energy = 0.0

        @ui.refreshable
        def zone_readout(energy: float, valence: float) -> None:
            from . import ZONE_CAPTIONS, ZONE_COLOURS

            category = mood_category(energy, valence)
            colour = ZONE_COLOURS.get(category, "#909090")
            caption = ZONE_CAPTIONS.get(category, category.replace("_", " ").title())
            fill_ink = "#ffffff" if category == "reckless_energy" else "#1c1a17"
            ui.label(caption).classes("w-full text-2xl font-black p-4 text-center").style(
                f"background:{colour};color:{fill_ink}"
            )

        with page_shell("Log"):
            ui.label("Log a mood").classes("text-3xl font-black")

            with ui.row().classes("w-full items-start gap-8 flex-wrap"):
                with ui.column().classes("items-center"):
                    pad = ui.interactive_image(
                        size=(PAD_WIDTH, PAD_HEIGHT),
                        events=["mousedown", "mousemove", "mouseup"],
                        cross=False,
                        content=zone_svg(marker=_mood_to_pixel(0.0, 0.0, PAD_WIDTH, PAD_HEIGHT)),
                        on_mouse=lambda e: handle_mouse(e),
                    )
                    # Its wrapper div is `position:relative; aspect-ratio:1/1` with no
                    # explicit width of its own -- it normally stretches to fill a
                    # block-level parent, but this column's items-center (needed to
                    # centre the readout label below it) makes flex children shrink
                    # to content instead, collapsing the pad to near-zero before its
                    # image has loaded. An explicit width fixes the aspect-ratio box.
                    pad.style(f"width:{PAD_WIDTH}px;max-width:100%")
                    pad.props("tabindex=0")
                    readout = ui.label(_readout(0.0, 0.0)).classes("mo-muted mo-tabular")

                with (
                    ui.column()
                    .classes("mo-surface mo-radius-0 border p-6 gap-4")
                    .style("border-width:2px;min-width:280px")
                ):
                    zone_readout(0.0, 0.0)
                    ui.button(
                        "Log this mood", color="high-energy-pleasant", on_click=lambda: log_mood()
                    ).classes("w-full")
                    notes = ui.textarea(label="Notes (optional)")
                    notes.props(f"maxlength={NOTES_MAX}")
                    ui.label("Arrow keys nudge. Enter logs.").classes("mo-muted text-xs")

        def set_mood(valence: float, energy: float) -> None:
            nonlocal current_valence, current_energy
            current_valence, current_energy = valence, energy
            pad.content = zone_svg(marker=_mood_to_pixel(valence, energy, PAD_WIDTH, PAD_HEIGHT))
            readout.text = _readout(energy, valence)
            zone_readout.refresh(energy, valence)

        def handle_mouse(event: events.MouseEventArguments) -> None:
            nonlocal dragging
            if event.type == "mousedown":
                dragging = True
            elif event.type == "mouseup":
                dragging = False
                return
            elif not dragging:
                return
            set_mood(*pixel_to_mood(event.image_x, event.image_y, PAD_WIDTH, PAD_HEIGHT))

        async def handle_key(event: events.GenericEventArguments) -> None:
            key = event.args.get("key", "")
            if key == "Enter":
                await log_mood()
                return
            valence, energy = nudge(current_valence, current_energy, key)
            if (valence, energy) != (current_valence, current_energy):
                set_mood(valence, energy)

        pad.on("keydown", handle_key, args=["key"])

        async def log_mood() -> None:
            username = app.storage.user.get("username")
            token = app.storage.user.get("token")
            if not username or not token:
                ui.notify("Please log in to record a mood.")
                ui.navigate.to("/login")
                return
            payload: dict = {"energy": current_energy, "valence": current_valence}
            note_text = (notes.value or "").strip()
            if note_text:
                payload["notes"] = note_text
            async with api.client() as http:
                response = await http.post(
                    f"/users/{username}/moods",
                    json=payload,
                    headers=api.auth_headers(token),
                )
            if response.status_code == 201:
                ui.notify("Mood logged!")
                notes.value = ""
                set_mood(0.0, 0.0)
            elif response.status_code == 401:
                ui.notify("Please log in to record a mood.")
                ui.navigate.to("/login")
            else:
                ui.notify("Could not complete the request.")
