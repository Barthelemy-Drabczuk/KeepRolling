"""The mood pad page, at `/`.

See ARCHITECTURE.md's FE-4 entry for the full contract: why
pixel_to_mood returns (valence, energy) -- the opposite of this
codebase's usual energy-first order, pinned by test_mood_pad.py -- the
exact SVG coordinates, why fill uses var(--q-{slot}) (confirmed safe
against NiceGUI's bundled DOMPurify profile, not a manual check), and
why cross=False (avoids colliding with the mousemove already in
events).
"""

from nicegui import app, events, ui

from . import api

PAD_WIDTH = 400
PAD_HEIGHT = 400
QUADRANT = 200


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


_QUADRANT_RECTS = (
    ("var(--q-high-energy-unpleasant)", 0, 0, QUADRANT, QUADRANT),
    ("var(--q-high-energy-pleasant)", QUADRANT, 0, QUADRANT, QUADRANT),
    ("var(--q-low-energy-unpleasant)", 0, QUADRANT, QUADRANT, QUADRANT),
    ("var(--q-low-energy-pleasant)", QUADRANT, QUADRANT, QUADRANT, QUADRANT),
)

_CAPTIONS = (
    ("Fuck it we ball", 100, 100, "#ffffff"),
    ("We are so fucking back", 290, 130, "#202020"),
    ("Let's fucking goooo", 320, 70, "#202020"),
    ("It is what it is", 130, 270, "#202020"),
    ("It's so over", 100, 300, "#202020"),
    ("Mom would be sad", 70, 330, "#202020"),
    ("We vibing", 300, 300, "#202020"),
)


def _pad_svg(marker_x: float, marker_y: float) -> str:
    parts = [
        f'<rect fill="{fill}" x="{x}" y="{y}" width="{w}" height="{h}" />'
        for fill, x, y, w, h in _QUADRANT_RECTS
    ]
    parts += [
        f'<text x="{x}" y="{y}" text-anchor="middle" font-family="sans-serif" '
        f'font-size="14" fill="{fill}">{caption}</text>'
        for caption, x, y, fill in _CAPTIONS
    ]
    parts.append(
        f'<circle cx="{marker_x:.1f}" cy="{marker_y:.1f}" r="9" fill="none" '
        f'stroke="#202020" stroke-width="4" />'
    )
    parts.append(
        f'<circle cx="{marker_x:.1f}" cy="{marker_y:.1f}" r="9" fill="none" '
        f'stroke="#ffffff" stroke-width="2" />'
    )
    return "".join(parts)


def create() -> None:
    """Register the / page."""

    @ui.page("/", title="Moodometer")
    def index() -> None:
        dragging = False
        current_valence = 0.0
        current_energy = 0.0

        def set_mood(valence: float, energy: float) -> None:
            nonlocal current_valence, current_energy
            current_valence, current_energy = valence, energy
            pad.content = _pad_svg(*_mood_to_pixel(valence, energy, PAD_WIDTH, PAD_HEIGHT))
            readout.text = _readout(energy, valence)

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

        def handle_key(event: events.GenericEventArguments) -> None:
            key = event.args.get("key", "")
            # FE-6b hooks in here: `if key == "Enter": await log_mood()` --
            # which makes this handler async, so keep that in mind rather
            # than adding a second keydown subscription.
            valence, energy = nudge(current_valence, current_energy, key)
            if (valence, energy) != (current_valence, current_energy):
                set_mood(valence, energy)

        pad = ui.interactive_image(
            size=(PAD_WIDTH, PAD_HEIGHT),
            events=["mousedown", "mousemove", "mouseup"],
            cross=False,
            content=_pad_svg(*_mood_to_pixel(0.0, 0.0, PAD_WIDTH, PAD_HEIGHT)),
            on_mouse=handle_mouse,
        )
        pad.props("tabindex=0")
        pad.on("keydown", handle_key, args=["key"])
        readout = ui.label(_readout(0.0, 0.0))

        async def log_mood() -> None:
            username = app.storage.user.get("username")
            token = app.storage.user.get("token")
            if not username or not token:
                # Nothing stored: same user-visible outcome as the API's 401, but
                # short-circuited here because f"/users/{None}/moods" would be a
                # wrong URL and f"/users//moods" matches no route (Starlette's
                # {username} is [^/]+), so either would 404 into the generic branch.
                ui.notify("Please log in to record a mood.")
                ui.navigate.to("/login")
                return
            async with api.client() as http:
                response = await http.post(
                    f"/users/{username}/moods",
                    json={"energy": current_energy, "valence": current_valence},
                    headers={"Authorization": f"Bearer {token}"},
                )
            if response.status_code == 201:
                ui.notify("Mood logged!")
                set_mood(0.0, 0.0)
            elif response.status_code == 401:
                ui.notify("Please log in to record a mood.")
                ui.navigate.to("/login")
            else:
                ui.notify("Could not complete the request.")

        ui.button("Log this mood", color="high-energy-pleasant", on_click=log_mood)
