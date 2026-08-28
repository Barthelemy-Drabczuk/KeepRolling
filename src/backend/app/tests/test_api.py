"""Unit tests for ``frontend/api.py``'s pure function (FE-12, REQ-UI-6).

FE-12 extracts the ``Authorization`` header literal that is currently
written inline at every authenticated call site in ``src/frontend/``:

    auth_headers(token: str) -> dict[str, str]
        return {"Authorization": f"Bearer {token}"}

As of 2026-08-29 that literal appears at seven call sites across four
modules — ``mood_pad.log_mood`` (1), ``history.history`` (1),
``journal._fetch_entries``/``_fetch_moods``/``save_entry`` (3), and
``analytics.analytics``'s statistics and moods fetches (2) — all
byte-identical, all naming the token ``token``. (ARCHITECTURE.md's FE-9a
and FE-9b notes say "fifth" and "sixth"; that running count is off by
one against the source, which is why REQ-UI-6 states the inventory
explicitly.)

This is a pure refactor: the helper must return *exactly* the dict those
seven sites build today, so that routing them through it is
behaviour-free. The tests below therefore pin the literal itself rather
than a looser "starts with Bearer" property — a helper that added a
second header, dropped the space, or special-cased a falsy token would
change behaviour at seven call sites at once.

``api.client()`` keeps its no-argument signature; nothing here touches
it. The import is done inside a helper rather than at module scope
because ``auth_headers`` does not exist yet, and a module-scope
``from frontend.api import auth_headers`` would turn the whole file into
a collection error instead of a set of individually failing tests.
"""

from typing import Callable

import pytest

# A realistically shaped token: the JWT ``auth.create_access_token``
# issues and ``app.storage.user["token"]`` holds, dots and all.
JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhbGljZSJ9.7Hx-9m0Qb1sVQoq2Zj4mXk8sT1lN0pRcAeF3gHiJkLm"


def _auth_headers() -> Callable[[str], dict[str, str]]:
    """Return ``frontend.api.auth_headers``."""
    from frontend.api import auth_headers

    return auth_headers


def test_auth_headers_sends_the_token_under_the_authorization_key() -> None:
    """The header name is ``Authorization`` and its value is the bearer token."""
    assert _auth_headers()(JWT) == {"Authorization": f"Bearer {JWT}"}


@pytest.mark.parametrize("token", [JWT, "short-token", "a.b.c"])
def test_auth_headers_interpolates_the_token_it_is_given(token: str) -> None:
    """The value is built from the argument, not from any captured token."""
    assert _auth_headers()(token)["Authorization"] == f"Bearer {token}"


def test_auth_headers_carries_only_the_authorization_key() -> None:
    """No extra header rides along: the seven call sites send exactly one."""
    assert list(_auth_headers()(JWT)) == ["Authorization"]


def test_auth_headers_separates_the_scheme_from_the_token_with_one_space() -> None:
    """``Bearer`` and the token are joined by a single space, per RFC 6750."""
    scheme, separator, remainder = _auth_headers()(JWT)["Authorization"].partition(" ")

    assert (scheme, separator, remainder) == ("Bearer", " ", JWT)


def test_auth_headers_does_not_special_case_an_empty_token() -> None:
    """A falsy token still interpolates: the helper is total, not a guard.

    Every call site already checks the token before calling, so this case
    never arises in practice; the test exists to stop an implementation
    from adding a ``return {}`` branch the seven inlined literals do not
    have.
    """
    assert _auth_headers()("") == {"Authorization": "Bearer "}
