"""Unit tests for ``frontend/export.py``'s pure function (FE-10, REQ-UI-7).

Named ``test_export_page.py`` rather than ``test_export.py``: that name is
already taken by the *backend* export endpoints' tests, the same collision
``test_analytics_page.py`` was named around.

Scope. FE-10's ``/export`` page has no page-load fetch and no auth guard,
so its whole runtime contract sits behind a click: read
``app.storage.user``, fetch the endpoint with a bearer token, hand the
response bytes to ``ui.download``. None of that is reachable from the
``client``/``TestClient`` fixture (``app.storage.user`` cannot be seeded
over HTTP) and ``nicegui.testing``'s fixtures are banned repo-wide, so it
is manual-verification-only. The page *shape* — the unguarded 200, the
three button captions, the nav link — is asserted in ``test_frontend.py``
beside the other pages' shape tests. What is left, and what this file
covers, is the one pure function in the module.

Why that function exists at all, since it looks like a detail worth
skipping: ``ui.download(content, filename, media_type)`` with a ``bytes``
``content`` becomes a client-side Blob download, and
``nicegui/static/nicegui.js:353`` sets ``anchor.download = filename || ""``.
A missing or empty filename therefore does not fall back to the server's
name — there is no server request to take a name from — it saves under a
browser-generated name with no extension. The server's name has to be
parsed out of ``Content-Disposition`` and passed in explicitly.

The header shapes below are the ones ``src/backend/app/app.py`` actually
emits (lines 931, 1047, 1212, all ``f"attachment; filename={filename}"``),
copied from the source rather than invented: **unquoted** values, one
space after the semicolon. That space is the trap the parametrized test
below exists to catch — a parser that splits on ``";"`` and checks
``startswith("filename=")`` without stripping sees ``" filename=..."`` and
falls back on every real response. No quoted-value case is tested because
the backend never emits one; adding a passing test for behaviour the
system does not have would pin a contract nobody asked for.

The import is done inside a helper rather than at module scope because
``frontend/export.py`` does not exist yet, and a module-scope import would
turn this whole file into one collection error instead of a set of
individually failing tests.
"""

from typing import Callable

import pytest

# A fixed date so the expected filenames read as literals rather than as a
# re-derivation of the server's `datetime.now().strftime('%Y%m%d')`.
CSV_HEADER = "attachment; filename=moodometer_alice_20260829.csv"
CSV_FILENAME = "moodometer_alice_20260829.csv"
JSON_HEADER = "attachment; filename=moodometer_alice_20260829.json"
JSON_FILENAME = "moodometer_alice_20260829.json"
PDF_HEADER = "attachment; filename=moodometer_report_alice_20260829.pdf"
PDF_FILENAME = "moodometer_report_alice_20260829.pdf"

FALLBACK = "moodometer.csv"


def _filename_from() -> Callable[[str, str], str]:
    """Return ``frontend.export._filename_from_content_disposition``."""
    from frontend.export import _filename_from_content_disposition

    return _filename_from_content_disposition


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (CSV_HEADER, CSV_FILENAME),
        (JSON_HEADER, JSON_FILENAME),
        (PDF_HEADER, PDF_FILENAME),
    ],
)
def test_filename_is_read_from_the_headers_filename_parameter(header: str, expected: str) -> None:
    """Each export endpoint's real header yields the name the server chose."""
    assert _filename_from()(header, FALLBACK) == expected


def test_filename_drops_the_parameter_name_and_the_disposition_type() -> None:
    """The result is the bare value: no ``filename=`` prefix, no ``attachment;``."""
    result = _filename_from()(CSV_HEADER, FALLBACK)

    assert "filename=" not in result
    assert "attachment" not in result


def test_filename_falls_back_when_the_response_carries_no_content_disposition() -> None:
    """A missing header (the caller passes "") yields the fallback, not "" or None."""
    assert _filename_from()("", FALLBACK) == FALLBACK


def test_filename_falls_back_when_the_header_names_no_filename_parameter() -> None:
    """A bare ``attachment`` disposition carries no name to use."""
    assert _filename_from()("attachment", FALLBACK) == FALLBACK


def test_filename_falls_back_when_the_filename_parameter_is_empty() -> None:
    """An empty value is the same broken download as no value: fall back.

    ``anchor.download = filename || ""`` treats "" exactly as it treats
    ``None``, so returning "" here would defeat the point of parsing the
    header in the first place.
    """
    assert _filename_from()("attachment; filename=", FALLBACK) == FALLBACK
