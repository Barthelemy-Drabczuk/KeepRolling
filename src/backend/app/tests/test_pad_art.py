"""Caption-placement geometry for ``frontend/pad_art.py`` (REQ-UI-11).

``tests/test_frontend.py`` already pins each of the seven zone captions'
*text* and its anchor point's quadrant. Neither pins how much room the
rendered glyphs actually take: a ``<text>`` whose anchor sits well inside
its zone still paints outside it once ``font-size`` x string length (x
``rotate(...)``) makes the rendered box wider than the zone holding it.
That is the VR-FLAG-4 bug -- user-confirmed in a browser for "We are so
fucking back" and "It is what it is".

**The metric model.** SVG text has no server-side measurable width, so
these tests compute an approximate box from a model stated here and in
REQ-UI-11, and assert *that* box stays inside the zone:

- Advance width per character: the Helvetica-Bold AFM table
  (``_ADVANCE``, units per 1000 em), times ``font-size``, times
  ``_WIDTH_FACTOR`` (1.1). The factor is deliberate: the pad renders in
  Archivo at ``font-weight="900"``, whose glyphs are wider than
  Helvetica-Bold's, so an unscaled table would under-report real width
  and let a genuine overflow pass.
- Vertical extent: ``_ASCENT`` (0.75 em) above the baseline, ``_DESCENT``
  (0.25 em) below it.
- Rotation: the unrotated box's four corners are rotated about the
  ``rotate(deg cx cy)`` centre, and the axis-aligned box of the rotated
  corners is what gets tested -- which is what a rotated ``<text>``
  visually occupies.

The model is an approximation, so it is applied conservatively: it is a
detector of real overflow, not a pixel-exact renderer. A caption that
fails here is genuinely painting outside its zone; a caption that passes
here by a hair may still be tight in a browser.

``_ZONE_REGIONS`` is a literal transcription of ``pad_art._ZONE_SHAPES``
resolved *through the paint order* -- each zone's remaining visible area
after every later shape paints over it, decomposed into disjoint
axis-aligned rectangles. It is a fourth hand-kept copy of that geometry
(alongside ``backend/app/analytics.py``'s and ``frontend/history.py``'s
``_ZONE_RECTS``), sanctioned for the same reason MC-4 sanctioned the
third: ``frontend/`` must never be imported into a shape this test could
share, and unlike those two, this table needs the carve-outs resolved
rather than the classifier's flat rect list. ``_ZONE_SHAPES`` itself is
frozen (VR-FLAG-1) -- if it ever changes, this table changes with it.

The dashed neutral band's "NEUTRAL" label is out of scope: it is a
leader-line annotation deliberately placed outside the band it labels,
and it is the only ``<text>`` in the drawing that is not
``text-anchor="middle"``, which is how these tests exclude it.
"""

import math
import re

import pytest

# Helvetica-Bold advance widths, units per 1000 em, for every character the
# seven captions use. See the module docstring for why the model is scaled.
_ADVANCE: dict[str, int] = {
    " ": 278,
    "'": 238,
    "F": 611,
    "I": 278,
    "L": 611,
    "M": 833,
    "W": 944,
    "a": 556,
    "b": 611,
    "c": 556,
    "d": 611,
    "e": 556,
    "f": 333,
    "g": 611,
    "h": 611,
    "i": 278,
    "k": 556,
    "l": 278,
    "m": 889,
    "n": 611,
    "o": 611,
    "s": 556,
    "t": 333,
    "u": 611,
    "v": 556,
    "w": 778,
    "y": 556,
}
_DEFAULT_ADVANCE = 600
_WIDTH_FACTOR = 1.1
_ASCENT = 0.75
_DESCENT = 0.25

# Visible area of each zone after the paint order in pad_art._ZONE_SHAPES,
# as disjoint (x_min, x_max, y_min, y_max) rectangles.
_ZONE_REGIONS: dict[str, tuple[tuple[float, float, float, float], ...]] = {
    # rect 0,0 200x130; nothing later paints over it
    "reckless_energy": ((0, 200, 0, 130),),
    # rect 200,0 200x200, less resigned_acceptance's upper band (x<266,
    # y>=130) and the peak_excitement corner (x>=336, y<60)
    "energetic_optimism": ((200, 266, 0, 130), (266, 336, 0, 200), (336, 400, 60, 200)),
    # rect 336,0 64x60; painted last in that corner
    "peak_excitement": ((336, 400, 0, 60),),
    # the L-shaped path M0,130 H266 V400 H204 V200 H0 Z
    "resigned_acceptance": ((0, 266, 130, 200), (204, 266, 200, 400)),
    # rect 0,200 204x200, less the deep_despair corner (x<66, y>=338)
    "sinking_despair": ((0, 204, 200, 338), (66, 204, 338, 400)),
    # rect 0,338 66x62; painted last in that corner
    "deep_despair": ((0, 66, 338, 400),),
    # rect 266,200 134x200; nothing later paints over it
    "relaxed_contentment": ((266, 400, 200, 400),),
}

# Which zone each caption names -- the same assignment frontend/history.py's
# _ZONE_RECTS comments carry.
_CAPTION_ZONE: dict[str, str] = {
    "Fuck it we ball": "reckless_energy",
    "We are so fucking back": "energetic_optimism",
    "Let's fucking goooo": "peak_excitement",
    "It is what it is": "resigned_acceptance",
    "It's so over": "sinking_despair",
    "Mom would be sad": "deep_despair",
    "We vibing": "relaxed_contentment",
}

_TEXT_RE = re.compile(r"<text\b([^>]*)>(.*?)</text>", re.DOTALL)
_ATTRS_RE = re.compile(r'([\w:.-]+)\s*=\s*"([^"]*)"')
_ROTATE_RE = re.compile(r"rotate\(\s*(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s*\)")


def _zone_svg() -> str:
    """Return the shared 8-zone drawing, marker-free."""
    from frontend.pad_art import zone_svg

    return zone_svg()


def _captions() -> dict[str, dict[str, str]]:
    """Return ``{caption: attributes}`` for every middle-anchored ``<text>``."""
    found = {}
    for match in _TEXT_RE.finditer(_zone_svg()):
        attrs = dict(_ATTRS_RE.findall(match.group(1)))
        if attrs.get("text-anchor") == "middle":
            found[match.group(2).strip()] = attrs
    return found


def _text_width(caption: str, size: float) -> float:
    """Approximate the rendered advance width of ``caption`` at ``size``."""
    units = sum(_ADVANCE.get(char, _DEFAULT_ADVANCE) for char in caption)
    return units / 1000 * size * _WIDTH_FACTOR


def _bounding_box(caption: str, attrs: dict[str, str]) -> tuple[float, float, float, float]:
    """Return the caption's ``(x_min, x_max, y_min, y_max)`` painted box."""
    x = float(attrs["x"])
    y = float(attrs["y"])
    size = float(attrs["font-size"])
    half = _text_width(caption, size) / 2
    corners = [
        (x - half, y - _ASCENT * size),
        (x + half, y - _ASCENT * size),
        (x + half, y + _DESCENT * size),
        (x - half, y + _DESCENT * size),
    ]

    rotate = _ROTATE_RE.search(attrs.get("transform", ""))
    if rotate is not None:
        degrees, cx, cy = (float(group) for group in rotate.groups())
        radians = math.radians(degrees)
        cos, sin = math.cos(radians), math.sin(radians)
        corners = [
            (
                (px - cx) * cos - (py - cy) * sin + cx,
                (px - cx) * sin + (py - cy) * cos + cy,
            )
            for px, py in corners
        ]

    xs = [point[0] for point in corners]
    ys = [point[1] for point in corners]
    return min(xs), max(xs), min(ys), max(ys)


def _outside(
    box: tuple[float, float, float, float],
    region: tuple[tuple[float, float, float, float], ...],
) -> list[tuple[float, float, float, float]]:
    """Return the parts of ``box`` no rectangle of ``region`` covers.

    Exact, not sampled: the box is cut into vertical slabs at every
    rectangle edge falling inside it, and each slab's y-range is checked
    against the merged y-intervals of the rectangles spanning that slab.
    """
    x_min, x_max, y_min, y_max = box
    edges = sorted({x_min, x_max} | {x for r in region for x in r[:2] if x_min < x < x_max})
    uncovered = []
    for left, right in zip(edges, edges[1:]):
        if right - left < 1e-9:
            continue
        spans = sorted((r[2], r[3]) for r in region if r[0] <= left + 1e-9 and r[1] >= right - 1e-9)
        reached = y_min
        for top, bottom in spans:
            if top > reached + 1e-9:
                break
            reached = max(reached, bottom)
        if reached < y_max - 1e-9:
            uncovered.append((left, right, reached, y_max))
    return uncovered


@pytest.mark.parametrize("caption", list(_CAPTION_ZONE))
def test_caption_is_painted_inside_its_own_zone(caption: str) -> None:
    """The caption's rendered box stays within the zone it names."""
    rendered = _captions()
    assert caption in rendered, f"no middle-anchored <text> carries the caption {caption!r}"

    zone = _CAPTION_ZONE[caption]
    box = _bounding_box(caption, rendered[caption])
    spill = _outside(box, _ZONE_REGIONS[zone])
    assert not spill, (
        f"{caption!r} paints outside {zone}: box "
        f"(x {box[0]:.1f}..{box[1]:.1f}, y {box[2]:.1f}..{box[3]:.1f}) "
        f"leaves the zone at {[tuple(round(v, 1) for v in part) for part in spill]}"
    )


def test_every_painted_caption_is_assigned_a_zone() -> None:
    """No middle-anchored caption escapes the placement check above."""
    unassigned = sorted(set(_captions()) - set(_CAPTION_ZONE))
    assert not unassigned, f"captions with no zone assignment to check against: {unassigned}"
