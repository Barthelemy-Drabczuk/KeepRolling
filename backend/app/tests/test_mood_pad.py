"""Unit tests for ``frontend/mood_pad.py``'s pixel -> mood mapping (FE-4).

FE-4 exposes the pad's coordinate mapping as a pure function so its
arithmetic gets a real red/green instead of falling under
ARCHITECTURE.md's manual-verification-only carve-out (which is about
*real mouse events*, not about arithmetic):

    pixel_to_mood(x: float, y: float, width: float, height: float)
        -> tuple[float, float]

    valence = x / width * 2 - 1
    energy  = 1 - y / height * 2

each clamped to [-1.0, 1.0] via min/max, because ``image_x``/``image_y``
can fall slightly outside ``size`` on fast pointer movement.

Return-tuple ORDER: these tests read the pair as ``(valence, energy)``,
following the order in which FE-4's own row states the two formulas
(valence first, mirroring the ``x``-then-``y`` parameter order). Note the
rest of the codebase names the pair the other way round (``MoodModel``,
``schemas``, the readout label, and FE-4's own "(energy=0.0, valence=0.0)"
all say energy first), so this one detail is worth confirming before
implementing — see the note in the FE-4 test report. Flipping it is a
one-line change to ``_pixel_to_mood``'s callers here; it must not be
"fixed" by making the implementation disagree with the tests.

The import is done inside a helper rather than at module scope on
purpose: ``frontend/mood_pad.py`` does not exist yet, and a module-scope
import would turn the whole file into a collection error rather than a
set of individually failing tests.
"""

from typing import Callable

import pytest

PAD_WIDTH = 400.0
PAD_HEIGHT = 400.0


def _pixel_to_mood() -> Callable[[float, float, float, float], tuple[float, float]]:
    """Return ``frontend.mood_pad.pixel_to_mood``."""
    from frontend.mood_pad import pixel_to_mood

    return pixel_to_mood


def test_top_left_corner_maps_to_unpleasant_high_energy() -> None:
    """Pixel (0, 0) is the most unpleasant, most energetic mood."""
    assert _pixel_to_mood()(0.0, 0.0, PAD_WIDTH, PAD_HEIGHT) == pytest.approx((-1.0, 1.0))


def test_top_right_corner_maps_to_pleasant_high_energy() -> None:
    """Pixel (width, 0) is the most pleasant, most energetic mood."""
    assert _pixel_to_mood()(400.0, 0.0, PAD_WIDTH, PAD_HEIGHT) == pytest.approx((1.0, 1.0))


def test_bottom_left_corner_maps_to_unpleasant_low_energy() -> None:
    """Pixel (0, height) is the most unpleasant, least energetic mood."""
    assert _pixel_to_mood()(0.0, 400.0, PAD_WIDTH, PAD_HEIGHT) == pytest.approx((-1.0, -1.0))


def test_bottom_right_corner_maps_to_pleasant_low_energy() -> None:
    """Pixel (width, height) is the most pleasant, least energetic mood."""
    assert _pixel_to_mood()(400.0, 400.0, PAD_WIDTH, PAD_HEIGHT) == pytest.approx((1.0, -1.0))


def test_centre_maps_to_the_origin_mood() -> None:
    """The pad's centre pixel is the neutral (0.0, 0.0) mood."""
    assert _pixel_to_mood()(200.0, 200.0, PAD_WIDTH, PAD_HEIGHT) == pytest.approx((0.0, 0.0))


def test_mapping_scales_to_the_given_pad_dimensions() -> None:
    """The mapping divides by the passed width/height, not by a hardcoded 400."""
    assert _pixel_to_mood()(150.0, 50.0, 300.0, 200.0) == pytest.approx((0.0, 0.5))


def test_x_beyond_the_right_edge_clamps_valence_to_one() -> None:
    """An x past the pad's right edge yields valence 1.0 rather than >1.0."""
    valence, _ = _pixel_to_mood()(420.0, 200.0, PAD_WIDTH, PAD_HEIGHT)

    assert valence == pytest.approx(1.0)


def test_x_left_of_the_pad_clamps_valence_to_minus_one() -> None:
    """A negative x yields valence -1.0 rather than <-1.0."""
    valence, _ = _pixel_to_mood()(-20.0, 200.0, PAD_WIDTH, PAD_HEIGHT)

    assert valence == pytest.approx(-1.0)


def test_y_above_the_top_edge_clamps_energy_to_one() -> None:
    """A negative y yields energy 1.0 rather than >1.0."""
    _, energy = _pixel_to_mood()(200.0, -20.0, PAD_WIDTH, PAD_HEIGHT)

    assert energy == pytest.approx(1.0)


def test_y_below_the_bottom_edge_clamps_energy_to_minus_one() -> None:
    """A y past the pad's bottom edge yields energy -1.0 rather than <-1.0."""
    _, energy = _pixel_to_mood()(200.0, 420.0, PAD_WIDTH, PAD_HEIGHT)

    assert energy == pytest.approx(-1.0)


def test_far_out_of_range_input_stays_within_the_model_range() -> None:
    """Wildly out-of-range pixels still map inside models.py's -1.0..1.0 range."""
    valence, energy = _pixel_to_mood()(5000.0, -5000.0, PAD_WIDTH, PAD_HEIGHT)

    assert -1.0 <= valence <= 1.0
    assert -1.0 <= energy <= 1.0
