"""The shared 8-zone circumplex drawing, reused by the log pad and analytics.

The 2026-09 redesign replaces the pad's plain 2x2 quadrant fill with the
irregular zone map from ``moodometer_chart.jpg`` ("THE MOOD METER"): eight
mood zones -- the same eight ``analytics.get_mood_quadrant_name`` classifies
into -- carved unevenly out of the four pinned quadrant colours. Both
``mood_pad.py`` (interactive, with a marker) and ``analytics.py`` (a static
"Where your moods land" backdrop, ``opacity=0.55``, no marker) draw from this
one module so the logging view and the analysis view are literally the same
instrument, per the frontend-designer contract's central design move.

Coordinate space is fixed at 400x400 (``x = (valence + 1) * 200``,
``y = (1 - energy) * 200``), matching ``mood_pad.PAD_WIDTH``/``PAD_HEIGHT``.
Four zones keep the pinned ``var(--q-{slot})`` quadrant fills (the FE-2
brand-palette hexes, untouched); the other four use new literal-hex zone
tokens from ``frontend.ZONE_COLOURS`` -- see that module for why they are
never duplicated as string literals here.

Caption note: the reference image renders "It is what it is" turning the
elbow corner as three separately-positioned fragments ("It is" / "what" /
"it is"). ``tests/test_frontend.py``'s ``test_mood_pad_captions_it_is_what_it_is``
pins the *whole phrase* as one ``<text>`` element's content, so this module
keeps every one of the seven captions -- including this one -- as a single
``<text>``, rotated as one unit rather than split into fragments. This is a
deliberate, narrower deviation from the frontend-designer contract's literal
three-fragment recommendation, made to keep that pinned test (and the
six others alongside it) green without a test amendment that would only
serve a cosmetic difference.
"""

INK = "#1c1a17"

S = 400  # pad side, pixels, matching mood_pad.PAD_WIDTH == PAD_HEIGHT

# Zone fills. reckless_energy/energetic_optimism/sinking_despair/
# relaxed_contentment use the pinned var(--q-{slot}) quadrant fills;
# the other four use ZONE_COLOURS' new literal hexes.
_ZONE_FILL: dict[str, str] = {
    "reckless_energy": "var(--q-high-energy-unpleasant)",
    "energetic_optimism": "var(--q-high-energy-pleasant)",
    "peak_excitement": "#ecd980",
    "resigned_acceptance": "#e8a05f",
    "sinking_despair": "var(--q-low-energy-unpleasant)",
    "deep_despair": "#8494b0",
    "relaxed_contentment": "var(--q-low-energy-pleasant)",
}

# (zone, svg_fragment) in draw order -- later entries paint over earlier ones,
# carving the smaller zones out of the four base quadrant blocks.
_ZONE_SHAPES: tuple[tuple[str, str], ...] = (
    ("energetic_optimism", '<rect x="200" y="0" width="200" height="200" />'),
    ("reckless_energy", '<rect x="0" y="0" width="200" height="130" />'),
    ("sinking_despair", '<rect x="0" y="200" width="204" height="200" />'),
    ("relaxed_contentment", '<rect x="266" y="200" width="134" height="200" />'),
    ("resigned_acceptance", '<path d="M0,130 H266 V400 H204 V200 H0 Z" />'),
    ("peak_excitement", '<rect x="336" y="0" width="64" height="60" />'),
    ("deep_despair", '<rect x="0" y="338" width="66" height="62" />'),
)

# caption, anchor (x, y), font-size, fill, optional rotate(deg cx cy)
_CAPTIONS: tuple[tuple[str, float, float, int, str, str], ...] = (
    ("Fuck it we ball", 100, 76, 26, "#ffffff", ""),
    ("We are so fucking back", 300, 105, 24, INK, "rotate(-38 300 105)"),
    ("Let's fucking goooo", 368, 32, 15, INK, ""),
    ("It is what it is", 160, 258, 22, INK, "rotate(18 160 258)"),
    ("It's so over", 100, 308, 26, INK, ""),
    ("Mom would be sad", 33, 370, 9, INK, ""),
    ("We vibing", 333, 300, 24, INK, ""),
)


def _zone_fills() -> str:
    parts = []
    for zone, shape in _ZONE_SHAPES:
        fill = _ZONE_FILL[zone]
        # Insert the fill (and a 1.5px ink keyline) into the shape's opening tag.
        tagged = shape.replace(" />", f' fill="{fill}" stroke="{INK}" stroke-width="1.5" />', 1)
        parts.append(tagged)
    return "".join(parts)


def _neutral_band() -> str:
    return (
        f'<rect x="180" y="180" width="40" height="40" fill="none" '
        f'stroke="{INK}" stroke-width="2" stroke-dasharray="4 3" />'
        f'<line x1="220" y1="180" x2="240" y2="160" stroke="{INK}" stroke-width="1" '
        f'stroke-dasharray="2 2" />'
        f'<text x="242" y="158" text-anchor="start" font-family="Archivo, sans-serif" '
        f'font-size="11" fill="{INK}">NEUTRAL</text>'
    )


def _captions() -> str:
    parts = []
    for caption, x, y, size, fill, rotate in _CAPTIONS:
        transform = f' transform="{rotate}"' if rotate else ""
        parts.append(
            f'<text x="{x}" y="{y}" text-anchor="middle" font-family="Archivo, sans-serif" '
            f'font-weight="900" font-size="{size}" fill="{fill}"{transform}>{caption}</text>'
        )
    return "".join(parts)


def _keyline() -> str:
    return (
        f'<rect x="0" y="0" width="{S}" height="{S}" fill="none" stroke="{INK}" stroke-width="3" />'
    )


def _marker(marker_x: float, marker_y: float) -> str:
    return (
        f'<line x1="0" y1="{marker_y:.1f}" x2="{marker_x:.1f}" y2="{marker_y:.1f}" '
        f'stroke="{INK}" stroke-width="1" stroke-dasharray="3 3" />'
        f'<line x1="{marker_x:.1f}" y1="{marker_y:.1f}" x2="{marker_x:.1f}" y2="{S}" '
        f'stroke="{INK}" stroke-width="1" stroke-dasharray="3 3" />'
        f'<circle cx="{marker_x:.1f}" cy="{marker_y:.1f}" r="9" fill="none" '
        f'stroke="{INK}" stroke-width="4" />'
        f'<circle cx="{marker_x:.1f}" cy="{marker_y:.1f}" r="9" fill="none" '
        f'stroke="#ffffff" stroke-width="2" />'
    )


def zone_svg(*, opacity: float = 1.0, marker: tuple[float, float] | None = None) -> str:
    """Build the 8-zone circumplex drawing shared by the log pad and analytics.

    ``opacity`` fades the zone fills/captions as one group -- analytics'
    static "Where your moods land" backdrop uses 0.55 so plotted points read
    clearly on top. ``marker`` is the pad's current-mood indicator in pixel
    coordinates; pass ``None`` for the non-interactive analytics panel.
    """
    parts = [f'<g opacity="{opacity}">', _zone_fills(), _neutral_band(), _captions(), "</g>"]
    parts.append(_keyline())
    if marker is not None:
        parts.append(_marker(*marker))
    return "".join(parts)
