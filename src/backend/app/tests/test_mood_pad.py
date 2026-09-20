"""Unit tests for ``frontend/mood_pad.py``'s pure functions.

Two of them: ``pixel_to_mood`` (FE-4), documented immediately below, and
``nudge`` (FE-6a), documented above its own tests at the end of the file.

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


# --- FE-6a: keyboard nudging ------------------------------------------------
#
#     nudge(valence: float, energy: float, key: str) -> tuple[float, float]
#
# ArrowUp/ArrowDown move energy by +STEP/-STEP, ArrowRight/ArrowLeft move
# valence by +STEP/-STEP (screen-relative: up = more energy, right = more
# pleasant, matching pixel_to_mood's inverted-y convention above). Each
# result is clamped to [-1.0, 1.0] and rounded to 2 decimal places; any
# other key returns the input unchanged.
#
# Return-tuple ORDER is (valence, energy) -- the same order pixel_to_mood
# uses and the same order as nudge's own parameters, so the handler in
# mood_pad.py can pipe one into set_mood(*...) exactly like the other.
#
# The rounding is a behavioural requirement, not a test convenience: the
# readout renders 2 decimals and the value is POSTed verbatim, so these
# tests assert exact float equality (`== 0.15`) rather than
# pytest.approx -- approx would pass on the un-rounded
# 0.15000000000000002 and let the drift through.
#
# Scope: the arithmetic only. The keydown subscription and real key-press
# dispatch are manual-verification-only per ARCHITECTURE.md's Testing
# policy; only focusability (tests/test_frontend.py) and this function are
# automated.

STEP = 0.05


def _nudge() -> Callable[[float, float, str], tuple[float, float]]:
    """Return ``frontend.mood_pad.nudge``."""
    from frontend.mood_pad import nudge

    return nudge


def test_arrow_up_raises_energy_by_one_step() -> None:
    """ArrowUp from the origin raises energy by 0.05 and leaves valence alone."""
    assert _nudge()(0.0, 0.0, "ArrowUp") == (0.0, STEP)


def test_arrow_down_lowers_energy_by_one_step() -> None:
    """ArrowDown from the origin lowers energy by 0.05 and leaves valence alone."""
    assert _nudge()(0.0, 0.0, "ArrowDown") == (0.0, -STEP)


def test_arrow_right_raises_valence_by_one_step() -> None:
    """ArrowRight from the origin raises valence by 0.05 and leaves energy alone."""
    assert _nudge()(0.0, 0.0, "ArrowRight") == (STEP, 0.0)


def test_arrow_left_lowers_valence_by_one_step() -> None:
    """ArrowLeft from the origin lowers valence by 0.05 and leaves energy alone."""
    assert _nudge()(0.0, 0.0, "ArrowLeft") == (-STEP, 0.0)


def test_arrow_up_clamps_energy_at_the_top_edge() -> None:
    """ArrowUp within one step of the top yields energy 1.0, not 1.03."""
    assert _nudge()(0.0, 0.98, "ArrowUp") == (0.0, 1.0)


def test_arrow_down_clamps_energy_at_the_bottom_edge() -> None:
    """ArrowDown within one step of the bottom yields energy -1.0, not -1.03."""
    assert _nudge()(0.0, -0.98, "ArrowDown") == (0.0, -1.0)


def test_arrow_right_clamps_valence_at_the_right_edge() -> None:
    """ArrowRight within one step of the right edge yields valence 1.0, not 1.03."""
    assert _nudge()(0.98, 0.0, "ArrowRight") == (1.0, 0.0)


def test_arrow_left_clamps_valence_at_the_left_edge() -> None:
    """ArrowLeft within one step of the left edge yields valence -1.0, not -1.03."""
    assert _nudge()(-0.98, 0.0, "ArrowLeft") == (-1.0, 0.0)


def test_repeated_nudges_do_not_accumulate_binary_float_drift() -> None:
    """Three ArrowUps land on exactly 0.15, not 0.15000000000000002."""
    nudge = _nudge()
    valence, energy = 0.0, 0.0
    for _ in range(3):
        valence, energy = nudge(valence, energy, "ArrowUp")

    assert energy == 0.15


@pytest.mark.parametrize("key", ["Enter", "Escape", "a", "Tab", ""])
def test_an_unrecognised_key_leaves_the_mood_unchanged(key: str) -> None:
    """Any non-arrow key is a no-op: nudge returns its input untouched."""
    assert _nudge()(0.3, -0.2, key) == (0.3, -0.2)


def test_branch_protection_verification_temporary() -> None:
    """Temporary: proves branch protection blocks merge on a failing check. Removed before merge."""
    assert False
