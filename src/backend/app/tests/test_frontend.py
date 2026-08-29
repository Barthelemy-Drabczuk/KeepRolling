"""Tests for the NiceGUI frontend mounted onto the FastAPI app.

Covers the server-observable half of FE-1, FE-2, FE-3a, FE-4, FE-5, FE-6a,
FE-7 and FE-8a; each item's section comment says what it deliberately leaves
to manual verification.
"""

import html
import json
import re

from fastapi.testclient import TestClient

# NiceGUI applies its palette client-side (colors.js sets --q-* in its
# mounted() hook), so CSS custom properties never appear in the server
# response. What *is* server-rendered is app.colors()'s serialized palette,
# emitted by nicegui/templates/index.html as:
#
#     const vue_config = {"brand":{...},"loadingBar":{...},"lang":{...}};
#
# Assert on that, not on --q-*. Custom colour names are normalized _ -> -
# by app.colors() before they reach the brand dict.
_VUE_CONFIG_RE = re.compile(r"const vue_config = (\{.*?\});")


def _brand_palette(client: TestClient) -> dict[str, str]:
    """Return the ``brand`` object serialized into GET /'s ``vue_config``."""
    response = client.get("/")
    assert response.status_code == 200

    match = _VUE_CONFIG_RE.search(response.text)
    assert match is not None, "GET / carried no `const vue_config = {...};` block"

    return json.loads(match.group(1))["brand"]


def test_root_page_serves_nicegui_placeholder(client) -> None:
    """GET / renders a NiceGUI page naming the app, not the old index.html."""
    response = client.get("/")

    assert response.status_code == 200
    assert "Moodometer" in response.text


def test_brand_palette_defines_high_energy_unpleasant(client) -> None:
    """The high-energy/unpleasant zone colour is bound in the Quasar palette."""
    assert _brand_palette(client).get("high-energy-unpleasant") == "#783020"


def test_brand_palette_defines_high_energy_pleasant(client) -> None:
    """The high-energy/pleasant zone colour is bound in the Quasar palette."""
    assert _brand_palette(client).get("high-energy-pleasant") == "#e0c080"


def test_brand_palette_defines_low_energy_unpleasant(client) -> None:
    """The low-energy/unpleasant zone colour is bound in the Quasar palette."""
    assert _brand_palette(client).get("low-energy-unpleasant") == "#98a8c0"


def test_brand_palette_defines_low_energy_pleasant(client) -> None:
    """The low-energy/pleasant zone colour is bound in the Quasar palette."""
    assert _brand_palette(client).get("low-energy-pleasant") == "#a0a888"


# --- FE-3a: the login and register pages' rendered shape ---------------------
#
# NiceGUI server-renders each page's initial element payload into the HTML,
# one `"props": {...}` object per element. Verified against NiceGUI 3.16.0:
# a page built from
#
#     ui.input("Username"); ui.input("Password", password=True)
#     ui.button("Log in", color="high-energy-pleasant")
#     ui.link("Register", "/register")
#
# renders these props objects (among others):
#
#     {"label": "Username", "type": "text", ...}
#     {"label": "Password", "type": "password", ...}
#     {"color": "high-energy-pleasant", "label": "Log in"}
#     {"href": "/register", "target": "_self"}
#
# These assert on those objects rather than on bare substrings, because a
# bare substring is not always evidence the page exists: `app.colors()` also
# serializes "high-energy-pleasant" into the Quasar brand palette of *every*
# NiceGUI response, including its 404 page. `"high-energy-pleasant" in
# response.text` therefore passes against a missing page — checked, it does.
# Requiring the colour and the caption on one element pins what FE-3a
# actually says: *the submit button* carries that colour.
#
# FE-3a covers page *shape* only. The interactive half (submitting the form,
# calling POST /auth/login, writing app.storage.user, navigating away) is
# FE-3b and is manual-verification-only: it runs over NiceGUI's websocket,
# which TestClient cannot drive. Nothing here asserts on it.
#
# "No server-side auth guard on either route" is pinned in the logged-out
# direction only: the `client` fixture is always a fresh, logged-out session,
# so a 200 here means a logged-out visitor is served the page. The
# already-logged-in direction is not TestClient-reachable (app.storage.user
# cannot be seeded over HTTP) and is left to FE-3b's manual verification.


_PROPS_RE = re.compile(r'"props":\s*(?=\{)')


def _rendered_props(client: TestClient, path: str) -> list[dict]:
    """Return every element's ``props`` object rendered into ``GET path``."""
    response = client.get(path)
    assert response.status_code == 200, f"GET {path} -> {response.status_code}"

    text = response.text
    objects: list[dict] = []
    for match in _PROPS_RE.finditer(text):
        depth = 0
        for index in range(match.end(), len(text)):
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
                if depth == 0:
                    objects.append(json.loads(text[match.end() : index + 1]))
                    break
    assert objects, f"GET {path} rendered no element props at all"
    return objects


def _has_props(client: TestClient, path: str, **expected) -> bool:
    """Does one single element on ``path`` carry all of ``expected``?"""
    return any(
        all(props.get(key) == value for key, value in expected.items())
        for props in _rendered_props(client, path)
    )


def test_login_page_is_served(client) -> None:
    """GET /login is served to a logged-out visitor rather than 404ing or redirecting."""
    assert client.get("/login").status_code == 200


def test_login_page_renders_username_field(client) -> None:
    """The login page offers a field labelled Username."""
    assert _has_props(client, "/login", label="Username")


def test_login_page_renders_masked_password_field(client) -> None:
    """The login page's Password field is masked rather than plain text."""
    assert _has_props(client, "/login", label="Password", type="password")


def test_login_page_renders_log_in_button(client) -> None:
    """The login page carries a submit button captioned "Log in"."""
    assert _has_props(client, "/login", label="Log in")


def test_login_page_button_uses_high_energy_pleasant(client) -> None:
    """The login page's "Log in" button itself carries FE-2's high-energy/pleasant colour."""
    assert _has_props(client, "/login", label="Log in", color="high-energy-pleasant")


def test_login_page_links_to_register(client) -> None:
    """The login page links across to /register."""
    assert _has_props(client, "/login", href="/register")


def test_register_page_is_served(client) -> None:
    """GET /register is served to a logged-out visitor rather than 404ing or redirecting."""
    assert client.get("/register").status_code == 200


def test_register_page_renders_username_field(client) -> None:
    """The register page offers a field labelled Username."""
    assert _has_props(client, "/register", label="Username")


def test_register_page_renders_masked_password_field(client) -> None:
    """The register page's Password field is masked rather than plain text."""
    assert _has_props(client, "/register", label="Password", type="password")


def test_register_page_renders_register_button(client) -> None:
    """The register page carries a submit button captioned "Register"."""
    assert _has_props(client, "/register", label="Register")


def test_register_page_button_uses_high_energy_pleasant(client) -> None:
    """The register page's "Register" button itself carries FE-2's high-energy/pleasant colour."""
    assert _has_props(client, "/register", label="Register", color="high-energy-pleasant")


def test_register_page_links_to_login(client) -> None:
    """The register page links back to /login."""
    assert _has_props(client, "/register", href="/login")


# --- FE-4: the mood pad's initial render at / --------------------------------
#
# The pad is `ui.interactive_image(size=(400, 400), events=[...], cross=False,
# content=<SVG>)` with no `src`. Verified against NiceGUI 3.16.0: that element
# server-renders into GET /'s HTML as
#
#     "4":{"tag":"nicegui-interactive_image","props":{
#       "content":"&lt;rect x=\"0\" ... fill=\"var(--q-high-energy-unpleasant)\" /&gt;...",
#       "src":"","events":["mousedown","mousemove","mouseup"],
#       "cross":false,"size":[400,400],"sanitize":true}}
#
# so `size`, `events` and the whole SVG `content` are reachable through the
# ordinary `client` fixture — no NiceGUI `user` fixture needed or permitted.
# Inside `content`, `<` and `>` are HTML-escaped to `&lt;`/`&gt;` while `"`
# and `'` are only JSON-escaped, so `content` has to be JSON-decoded *and*
# `html.unescape`d before it can be read as SVG.
#
# These use a dedicated extractor rather than `_rendered_props` above: that
# helper scans brace depth from `"props":` and would mis-parse any `{`/`}`
# inside the SVG string. `json.JSONDecoder().raw_decode` respects string
# boundaries and escapes, so it stays correct whatever the SVG contains.
#
# Colour literal: FE-4 says `fill="var(--q-{slot})"` for FE-2's four slot
# names. NiceGUI's `app.colors()` normalizes `_` -> `-` before the names ever
# reach the browser (the FE-2 tests above assert the hyphenated keys), so the
# CSS custom property that actually resolves is `--q-high-energy-unpleasant`,
# not `--q-high_energy_unpleasant`. The hyphenated form is asserted here.
#
# Scope: the *initial* render only. Pointer dragging, the marker following
# the cursor, and the readout label updating during a drag run over NiceGUI's
# websocket, which TestClient cannot drive; they stay manual-verification-only
# per ARCHITECTURE.md's Testing policy, and nothing here asserts on them.

PAD_SIZE = 400
QUADRANT = PAD_SIZE / 2

_TAG_RE = re.compile(r'"tag":\s*"nicegui-interactive_image"')
_TEXT_RE = re.compile(r'"text":\s*(?=")')
_ATTRS_RE = re.compile(r'([\w:.-]+)\s*=\s*"([^"]*)"')

# FE-4's fixed caption -> quadrant assignment, in the row's reading order
# (most-central to most-extreme).
HIGH_ENERGY_UNPLEASANT_CAPTIONS = ["Fuck it we ball"]
HIGH_ENERGY_PLEASANT_CAPTIONS = ["We are so fucking back", "Let's fucking goooo"]
LOW_ENERGY_UNPLEASANT_CAPTIONS = ["It is what it is", "It's so over", "Mom would be sad"]
LOW_ENERGY_PLEASANT_CAPTIONS = ["We vibing"]


def _pad_props(client: TestClient) -> dict:
    """Return the ``props`` object of the ``interactive_image`` pad on GET /."""
    response = client.get("/")
    assert response.status_code == 200, f"GET / -> {response.status_code}"

    text = response.text
    tag = _TAG_RE.search(text)
    assert tag is not None, "GET / rendered no nicegui-interactive_image element"

    props_key = text.find('"props"', tag.end())
    assert props_key != -1, "the mood pad element rendered without a props object"

    props, _ = json.JSONDecoder().raw_decode(text, text.index("{", props_key))
    return props


def _pad_content(client: TestClient) -> str:
    """Return the pad's SVG ``content``, JSON-decoded and HTML-unescaped."""
    content = _pad_props(client).get("content", "")
    assert content, "the mood pad rendered with an empty SVG content prop"
    return html.unescape(content)


def _svg_tags(content: str, tag: str) -> list[dict[str, str]]:
    """Return one attribute dict per ``<tag ...>`` element in ``content``."""
    return [
        dict(_ATTRS_RE.findall(match.group(1)))
        for match in re.finditer(rf"<{tag}\b([^>]*?)/?>", content)
    ]


def _svg_texts(content: str) -> list[tuple[str, dict[str, str]]]:
    """Return ``(caption, attributes)`` for every ``<text>`` element."""
    return [
        (match.group(2).strip(), dict(_ATTRS_RE.findall(match.group(1))))
        for match in re.finditer(r"<text\b([^>]*)>(.*?)</text>", content, re.DOTALL)
    ]


def _rect_filled_with(content: str, slot: str) -> dict[str, str]:
    """Return the single ``<rect>`` filled with FE-2's ``slot`` colour."""
    rects = [rect for rect in _svg_tags(content, "rect") if rect.get("fill") == f"var(--q-{slot})"]
    assert len(rects) == 1, f'expected one <rect fill="var(--q-{slot})">, found {len(rects)}'
    return rects[0]


def _assert_covers_quadrant(rect: dict[str, str], left: float, top: float) -> None:
    """Assert ``rect`` covers the 200x200 quadrant anchored at (left, top)."""
    box = (
        float(rect.get("x", "nan")),
        float(rect.get("y", "nan")),
        float(rect.get("width", "nan")),
        float(rect.get("height", "nan")),
    )
    assert box == (left, top, QUADRANT, QUADRANT), f"rect {box} is not the quadrant at {left},{top}"


def _assert_captions_in_quadrant(
    content: str, captions: list[str], left: float, top: float
) -> None:
    """Assert each of ``captions`` is placed inside the given quadrant."""
    placed = {caption: attrs for caption, attrs in _svg_texts(content)}
    for caption in captions:
        assert caption in placed, f"no <text> element carries the caption {caption!r}"
        x = float(placed[caption].get("x", "nan"))
        y = float(placed[caption].get("y", "nan"))
        assert left <= x <= left + QUADRANT, f"{caption!r} sits at x={x}, outside its quadrant"
        assert top <= y <= top + QUADRANT, f"{caption!r} sits at y={y}, outside its quadrant"


def _rendered_texts(client: TestClient, path: str) -> list[str]:
    """Return the rendered ``text`` of every element on ``GET path``."""
    response = client.get(path)
    assert response.status_code == 200, f"GET {path} -> {response.status_code}"

    decoder = json.JSONDecoder()
    return [
        decoder.raw_decode(response.text, match.end())[0]
        for match in _TEXT_RE.finditer(response.text)
    ]


def test_root_page_renders_the_mood_pad(client) -> None:
    """GET / renders an interactive_image mood pad, not FE-1's bare placeholder label."""
    assert _pad_props(client)


def test_mood_pad_is_400_by_400_pixels(client) -> None:
    """The mood pad declares a 400x400 pixel coordinate space."""
    assert _pad_props(client)["size"] == [PAD_SIZE, PAD_SIZE]


def test_mood_pad_subscribes_to_drag_mouse_events(client) -> None:
    """The pad subscribes to mousedown/mousemove/mouseup, not interactive_image's default click."""
    assert _pad_props(client)["events"] == ["mousedown", "mousemove", "mouseup"]


def test_mood_pad_fills_top_left_with_high_energy_unpleasant(client) -> None:
    """The top-left quadrant is filled with FE-2's high-energy/unpleasant colour."""
    content = _pad_content(client)

    _assert_covers_quadrant(_rect_filled_with(content, "high-energy-unpleasant"), 0.0, 0.0)


def test_mood_pad_fills_top_right_with_high_energy_pleasant(client) -> None:
    """The top-right quadrant is filled with FE-2's high-energy/pleasant colour."""
    content = _pad_content(client)

    _assert_covers_quadrant(_rect_filled_with(content, "high-energy-pleasant"), QUADRANT, 0.0)


def test_mood_pad_fills_bottom_left_with_low_energy_unpleasant(client) -> None:
    """The bottom-left quadrant is filled with FE-2's low-energy/unpleasant colour."""
    content = _pad_content(client)

    _assert_covers_quadrant(_rect_filled_with(content, "low-energy-unpleasant"), 0.0, QUADRANT)


def test_mood_pad_fills_bottom_right_with_low_energy_pleasant(client) -> None:
    """The bottom-right quadrant is filled with FE-2's low-energy/pleasant colour."""
    content = _pad_content(client)

    _assert_covers_quadrant(_rect_filled_with(content, "low-energy-pleasant"), QUADRANT, QUADRANT)


def test_mood_pad_captions_fuck_it_we_ball(client) -> None:
    """The pad carries the caption "Fuck it we ball" verbatim."""
    assert "Fuck it we ball" in [caption for caption, _ in _svg_texts(_pad_content(client))]


def test_mood_pad_captions_we_are_so_fucking_back(client) -> None:
    """The pad carries the caption "We are so fucking back" verbatim."""
    assert "We are so fucking back" in [caption for caption, _ in _svg_texts(_pad_content(client))]


def test_mood_pad_captions_lets_fucking_goooo(client) -> None:
    """The pad carries the caption "Let's fucking goooo" verbatim, apostrophe included."""
    assert "Let's fucking goooo" in [caption for caption, _ in _svg_texts(_pad_content(client))]


def test_mood_pad_captions_it_is_what_it_is(client) -> None:
    """The pad carries the caption "It is what it is" verbatim."""
    assert "It is what it is" in [caption for caption, _ in _svg_texts(_pad_content(client))]


def test_mood_pad_captions_its_so_over(client) -> None:
    """The pad carries the caption "It's so over" verbatim, apostrophe included."""
    assert "It's so over" in [caption for caption, _ in _svg_texts(_pad_content(client))]


def test_mood_pad_captions_mom_would_be_sad(client) -> None:
    """The pad carries the caption "Mom would be sad" verbatim."""
    assert "Mom would be sad" in [caption for caption, _ in _svg_texts(_pad_content(client))]


def test_mood_pad_captions_we_vibing(client) -> None:
    """The pad carries the caption "We vibing" verbatim."""
    assert "We vibing" in [caption for caption, _ in _svg_texts(_pad_content(client))]


def test_high_energy_unpleasant_caption_sits_in_its_quadrant(client) -> None:
    """The high-energy/unpleasant caption is placed in the top-left quadrant."""
    content = _pad_content(client)

    _assert_captions_in_quadrant(content, HIGH_ENERGY_UNPLEASANT_CAPTIONS, 0.0, 0.0)


def test_high_energy_pleasant_captions_sit_in_their_quadrant(client) -> None:
    """Both high-energy/pleasant captions are placed in the top-right quadrant."""
    content = _pad_content(client)

    _assert_captions_in_quadrant(content, HIGH_ENERGY_PLEASANT_CAPTIONS, QUADRANT, 0.0)


def test_low_energy_unpleasant_captions_sit_in_their_quadrant(client) -> None:
    """All three low-energy/unpleasant captions are placed in the bottom-left quadrant."""
    content = _pad_content(client)

    _assert_captions_in_quadrant(content, LOW_ENERGY_UNPLEASANT_CAPTIONS, 0.0, QUADRANT)


def test_low_energy_pleasant_caption_sits_in_its_quadrant(client) -> None:
    """The low-energy/pleasant caption is placed in the bottom-right quadrant."""
    content = _pad_content(client)

    _assert_captions_in_quadrant(content, LOW_ENERGY_PLEASANT_CAPTIONS, QUADRANT, QUADRANT)


def test_mood_pad_marker_starts_at_the_pad_centre(client) -> None:
    """The pad's marker is drawn at (200, 200) — the initial energy=0.0, valence=0.0 mood."""
    centres = [
        (float(circle.get("cx", "nan")), float(circle.get("cy", "nan")))
        for circle in _svg_tags(_pad_content(client), "circle")
    ]

    assert (QUADRANT, QUADRANT) in centres, f"no marker <circle> at the pad centre; found {centres}"


def test_root_page_renders_the_initial_mood_readout(client) -> None:
    """A readout label on / starts at the origin mood, "Energy: 0.00 · Valence: 0.00"."""
    assert "Energy: 0.00 · Valence: 0.00" in _rendered_texts(client, "/")


# --- FE-5: the confirm button's initial render at / --------------------------
#
# Only the button's *initial render* is server-observable, so only that is
# tested here. Everything else FE-5 specifies -- the click handler, the
# authenticated POST /users/{username}/moods, the 201/401/other branches, the
# live readout updates and the marker reset -- is dispatched over NiceGUI's
# websocket after the page is served, is unreachable through TestClient, and
# is manual-verification-only per ARCHITECTURE.md's Testing policy. Per that
# same policy nicegui.testing's `user`/`Screen` fixtures are not used to reach
# it either.
#
# The endpoint the handler will call is already covered below the UI in
# tests/test_moods.py (REQ-MOOD-1/2/5); FE-5 must not re-test it through the
# frontend.

CONFIRM_CAPTION = "Log this mood"


def _confirm_button_props(client: TestClient) -> dict:
    """Return the rendered ``props`` of /'s confirm button, by its caption."""
    matches = [
        props for props in _rendered_props(client, "/") if props.get("label") == CONFIRM_CAPTION
    ]
    assert matches, f"GET / rendered no element labelled {CONFIRM_CAPTION!r}"

    return matches[0]


def test_root_page_renders_the_confirm_button(client) -> None:
    """GET / renders a button captioned "Log this mood" below the pad's readout."""
    assert _has_props(client, "/", label=CONFIRM_CAPTION)


def test_confirm_button_uses_high_energy_pleasant(client) -> None:
    """The confirm button is coloured with FE-2's high-energy/pleasant brand slot."""
    assert _has_props(client, "/", label=CONFIRM_CAPTION, color="high-energy-pleasant")


def test_confirm_button_is_enabled_at_initial_render(client) -> None:
    """The confirm button is live from page load: the untouched marker is already a valid mood.

    NiceGUI writes ``_props['disable'] = not enabled`` only via
    DisableableElement._handle_enabled_change, and an enabled button renders no
    ``disable`` key at all -- so "not disabled" is `disable` being absent or
    false, never `disable is False`.
    """
    assert _confirm_button_props(client).get("disable") is not True


# --- FE-6a: the pad is keyboard-focusable ------------------------------------
#
# Only the pad's *focusability* is server-observable: `pad.props('tabindex=0')`
# renders into GET /'s HTML as a `"tabindex":"0"` entry in the pad element's
# props (NiceGUI's props parser stores the value as the string "0", not the
# int 0). Everything else FE-6a specifies -- the `.on('keydown', ...)`
# subscription, real key-press dispatch, and the marker/readout updates that
# follow -- runs over NiceGUI's websocket, is unreachable through TestClient,
# and is manual-verification-only per ARCHITECTURE.md's Testing policy.
#
# The nudge arithmetic itself is covered as a plain unit test in
# tests/test_mood_pad.py; nothing here re-tests it through the frontend.
#
# This reads `_pad_props` rather than `_has_props`: the requirement is about
# *the pad's* props specifically, and `_has_props` would also be satisfied by
# a tabindex on any other element on the page.


def test_mood_pad_is_keyboard_focusable(client) -> None:
    """The pad renders with tabindex="0", so it can take keyboard focus."""
    assert _pad_props(client).get("tabindex") == "0"


# --- FE-7: the history page's logged-out render, and its link from / ---------
#
# Only two things about FE-7 are server-observable, and only those are
# tested here:
#
#   1. /history is unguarded (D1 resolved to "no guard", consistent with
#      /, /login and /register) and, to a logged-out visitor, renders the
#      empty-state prompt instead of a table.
#   2. / carries a `ui.link("History", "/history")` so the page is
#      reachable.
#
# Everything FE-7 specifies behind an authenticated fetch -- the
# populated table and its four columns, the newest-first ordering, the
# timestamp/2-decimal formatting, the zero-mood-but-logged-in empty
# state, and both the 401 and generic-failure branches -- depends on
# `app.storage.user["token"]`, which cannot be seeded over HTTP. Per
# ARCHITECTURE.md's Testing policy that is manual-verification-only, and
# nicegui.testing's `user`/`Screen` fixtures are not used to reach it.
# The `quadrant_label` arithmetic those rows depend on is covered as a
# plain unit test in tests/test_history.py; nothing here re-tests it
# through the frontend.
#
# The status test passes `follow_redirects=False` deliberately.
# TestClient follows redirects by default, so a plain
# `client.get("/history").status_code == 200` would also pass against an
# auth guard that 307s a logged-out visitor to /login -- i.e. it would
# pass under *either* resolution of D1 and pin nothing. Asserting on the
# unfollowed response is what makes "no guard" testable.

HISTORY_EMPTY_PROMPT = "No mood entries yet. Click on the mood board to record your first mood!"


def test_history_page_is_served_without_an_auth_guard(client) -> None:
    """GET /history returns 200 to a logged-out visitor rather than redirecting to /login."""
    response = client.get("/history", follow_redirects=False)

    assert response.status_code == 200


def test_history_page_shows_the_empty_prompt_when_logged_out(client) -> None:
    """A logged-out visitor to /history sees FE-7's empty-state prompt, not a table."""
    response = client.get("/history", follow_redirects=False)

    assert HISTORY_EMPTY_PROMPT in response.text


def test_root_page_links_to_history(client) -> None:
    """The pad page links across to /history, making the history page reachable."""
    assert _has_props(client, "/", href="/history")


# --- FE-8a: the journal page's logged-out render, and its link from / ---------
#
# Same three-assertion shape as FE-7 above, for the same reason: only the
# unguarded route, the logged-out prompt, and the link that makes the page
# reachable are server-observable.
#
# Everything else FE-8a specifies sits behind an authenticated fetch of
# GET /users/{username}/entries -- the populated ui.card list, the
# newest-first order, the "%Y-%m-%d %H:%M UTC" timestamp format, the
# zero-entry-but-logged-in empty state, and both the 401 and
# generic-failure branches. All of those depend on app.storage.user, which
# cannot be seeded over HTTP, so per ARCHITECTURE.md's Testing policy they
# are manual-verification-only, and nicegui.testing's `user`/`Screen`
# fixtures are not used to reach them (they are banned repo-wide).
#
# FE-8a deliberately introduces *no* new pure function, so there is no
# tests/test_journal.py yet. Its one helper, `_format_timestamp`, is the
# sanctioned second copy of frontend/history.py's private two-liner, and
# FE-7 did not unit-test that one either -- pinning it in a second place
# would assert the same `datetime.fromisoformat(...).strftime(...)` call
# twice without pinning anything FE-7 has not already fixed. The first
# FE-8 unit tests land with FE-8c's `mood_line`/`mood_option_label`.
#
# The empty prompt is asserted verbatim and is deliberately CTA-free:
# FE-8b adds a compose box to this same page and must keep this string
# unchanged, so it cannot say "write your first one above" while no such
# box exists.
#
# As with /history, the status test passes follow_redirects=False on
# purpose: TestClient follows redirects by default, so a plain
# client.get("/journal").status_code == 200 would also pass against a
# guard that 307s a logged-out visitor to /login, pinning nothing.

JOURNAL_EMPTY_PROMPT = "No journal entries yet."


def test_journal_page_is_served_without_an_auth_guard(client) -> None:
    """GET /journal returns 200 to a logged-out visitor rather than redirecting to /login."""
    response = client.get("/journal", follow_redirects=False)

    assert response.status_code == 200


def test_journal_page_shows_the_empty_prompt_when_logged_out(client) -> None:
    """A logged-out visitor to /journal sees FE-8a's empty-state prompt, not a list."""
    response = client.get("/journal", follow_redirects=False)

    assert JOURNAL_EMPTY_PROMPT in response.text


def test_root_page_links_to_journal(client) -> None:
    """The pad page links across to /journal, making the journal page reachable."""
    assert _has_props(client, "/", href="/journal")


# --- FE-8b: the journal compose form's initial render at /journal -------------
#
# FE-8b names exactly one server-observable thing: the compose form renders
# for a *logged-out* visitor too (matching /'s pad+button, which render
# logged-out and short-circuit on click), so the `client` fixture -- always a
# fresh, logged-out session -- can see the textarea's label and the button's
# caption/colour on GET /journal. That is the whole automated surface.
#
# Everything else FE-8b specifies runs over NiceGUI's websocket after the page
# is served and is manual-verification-only per ARCHITECTURE.md's Testing
# policy: the click handler, the client-side 1-5000 validation notify, the
# logged-out short-circuit notify + navigation, the authenticated POST
# /users/{username}/entries, all three response branches (201/401/other), the
# textarea clear, and the @ui.refreshable list re-render. Per that same policy
# nicegui.testing's `user`/`Screen` fixtures are not used to reach them. FE-8b
# has five enumerated manual acceptance steps covering exactly those.
#
# The endpoint the handler will call is already covered below the UI in
# tests/test_entries.py (REQ-ENTRY-1/3); FE-8b must not re-test it through the
# frontend.
#
# Verified against NiceGUI 3.16.0's source rather than assumed:
#
#   * `ui.textarea` (nicegui/elements/textarea.py) subclasses `Input` and sets
#     `self._props['type'] = 'textarea'`, so a textarea is distinguishable
#     from a plain `ui.input` in the rendered props -- same discriminator the
#     FE-3a password tests use. `label=` lands in props verbatim.
#   * `.props("maxlength=5000")` goes through `Props.parse`
#     (nicegui/props.py), whose unquoted branch stores the value as the
#     *string* "5000" -- the same string-not-int behaviour FE-6a's
#     `tabindex=0` test documents. `str(...)` is applied below so the
#     assertion holds whichever form reaches props.
#   * Quasar honours it: `useFieldProps` declares `maxlength: [Number,
#     String]` and QInput's control renderer binds `maxlength:
#     props.maxlength` onto the native element it renders for `type ===
#     "textarea"` (nicegui/static/quasar.umd.js). So the hard input-level cap
#     FE-8b asks for is real, not decorative.
#   * `@ui.refreshable` (nicegui/functions/refreshable.py) still wraps the
#     function in a `refreshable` object exposing `.refresh(*args,
#     **kwargs)`, which clears each target's container and re-runs the
#     function; async functions are supported (`_execute_refresh` collects
#     awaitables). Nothing about the list's re-render is server-observable, so
#     nothing here asserts on it.
#
# FE-8a's "No journal entries yet." prompt is deliberately left untouched
# above: FE-8b keeps it verbatim, so
# test_journal_page_shows_the_empty_prompt_when_logged_out must keep passing
# unchanged once the compose form lands.

COMPOSE_LABEL = "New journal entry"
COMPOSE_CAPTION = "Save entry"
COMPOSE_MAXLENGTH = "5000"


def test_journal_page_renders_the_compose_textarea(client) -> None:
    """A logged-out visitor to /journal sees a multi-line "New journal entry" field."""
    assert _has_props(client, "/journal", label=COMPOSE_LABEL, type="textarea")


def test_journal_compose_textarea_caps_input_at_5000_characters(client) -> None:
    """The compose textarea carries maxlength=5000, REQ-ENTRY-1's cap, at the input level."""
    matches = [
        props
        for props in _rendered_props(client, "/journal")
        if props.get("label") == COMPOSE_LABEL
    ]
    assert matches, f"GET /journal rendered no element labelled {COMPOSE_LABEL!r}"

    assert str(matches[0].get("maxlength")) == COMPOSE_MAXLENGTH


def test_journal_page_renders_the_save_entry_button(client) -> None:
    """A logged-out visitor to /journal sees a button captioned "Save entry"."""
    assert _has_props(client, "/journal", label=COMPOSE_CAPTION)


def test_journal_save_entry_button_uses_high_energy_pleasant(client) -> None:
    """The "Save entry" button itself carries FE-2's high-energy/pleasant colour."""
    assert _has_props(client, "/journal", label=COMPOSE_CAPTION, color="high-energy-pleasant")


# --- FE-9a: the analytics page's logged-out render, and its link from / -------
#
# Same three-assertion shape as FE-7 and FE-8a above, for the same reason:
# only the unguarded route, the logged-out prompt, and the link that makes
# the page reachable are server-observable.
#
# Everything else FE-9a specifies sits behind an authenticated fetch of
# GET /users/{username}/analytics/statistics -- the distribution bar chart,
# the zero-mood-but-logged-in empty state, and both the 401 and
# generic-failure branches. All depend on app.storage.user, which cannot be
# seeded over HTTP, so per ARCHITECTURE.md's Testing policy they are
# manual-verification-only, and nicegui.testing's `user`/`Screen` fixtures
# are not used to reach them (banned repo-wide).
#
# Worth recording, because it is counter-intuitive and was checked rather
# than assumed: ui.echart *would* be server-observable if the chart ever
# rendered for a logged-out visitor. NiceGUI 3.16.0 stores the whole
# options dict as the element's `options` prop, and an empirical probe
# confirmed series names, numeric data and itemStyle colours all survive
# into GET /'s HTML and parse through _rendered_props above. The chart is
# untestable here not because echart hides its options, but because FE-9a
# renders no chart at all without a token. That is why the options-building
# arithmetic is a pure function unit-tested in tests/test_analytics_page.py
# instead -- the same split FE-4 made for pixel_to_mood.
#
# As with /history and /journal, the status test passes
# follow_redirects=False on purpose: TestClient follows redirects by
# default, so a plain client.get("/analytics").status_code == 200 would
# also pass against a guard that 307s a logged-out visitor to /login,
# pinning nothing.

ANALYTICS_EMPTY_PROMPT = "No mood data to analyse yet."


def test_analytics_page_is_served_without_an_auth_guard(client) -> None:
    """GET /analytics returns 200 to a logged-out visitor rather than redirecting to /login."""
    response = client.get("/analytics", follow_redirects=False)

    assert response.status_code == 200


def test_analytics_page_shows_the_empty_prompt_when_logged_out(client) -> None:
    """A logged-out visitor to /analytics sees FE-9a's empty-state prompt, not a chart."""
    response = client.get("/analytics", follow_redirects=False)

    assert ANALYTICS_EMPTY_PROMPT in response.text


def test_root_page_links_to_analytics(client) -> None:
    """The pad page links across to /analytics, making the analytics page reachable."""
    assert _has_props(client, "/", href="/analytics")


# --- FE-10: the export page's rendered shape, and its link from / -------------
#
# /export differs from /history, /journal and /analytics in one way that
# makes it *more* server-observable, not less: it has no page-load fetch at
# all, so a logged-out visitor is served the same three buttons a logged-in
# one is. There is no logged-out empty prompt to assert -- the buttons are
# the page -- and no fetch-failure branch reachable on GET.
#
# Everything after the click is manual-verification-only, for the usual
# reason: the handler reads app.storage.user, which cannot be seeded over
# HTTP, and nicegui.testing's user/Screen fixtures are banned repo-wide.
# That covers the GET of /users/{username}/export/{csv,json,pdf}, the
# ui.download call, and all three response branches (200 -> download,
# 401 -> login prompt + navigate, anything else -> generic notify).
#
# Each button is asserted on caption *and* colour together, per the FE-3a
# note above: a bare substring is not evidence, since app.colors()
# serializes "high-energy-pleasant" into every NiceGUI response including
# its 404 page. Requiring both on one element pins that *the download
# button* is what carries the caption.
#
# The status test passes follow_redirects=False for the same reason FE-7,
# FE-8a and FE-9a's do: TestClient follows redirects by default, so a plain
# 200 check would also pass against a guard that 307s to /login.


def test_export_page_is_served_without_an_auth_guard(client) -> None:
    """GET /export returns 200 to a logged-out visitor rather than redirecting to /login."""
    response = client.get("/export", follow_redirects=False)

    assert response.status_code == 200


def test_export_page_offers_a_csv_download_button(client) -> None:
    """The export page offers a CSV download, captioned and coloured like every action button."""
    assert _has_props(client, "/export", label="Download CSV", color="high-energy-pleasant")


def test_export_page_offers_a_json_download_button(client) -> None:
    """The export page offers a JSON download alongside the CSV one."""
    assert _has_props(client, "/export", label="Download JSON", color="high-energy-pleasant")


def test_export_page_offers_a_pdf_download_button(client) -> None:
    """The export page offers a PDF download alongside the CSV and JSON ones."""
    assert _has_props(client, "/export", label="Download PDF", color="high-energy-pleasant")


def test_root_page_links_to_export(client) -> None:
    """The pad page links across to /export, making the export page reachable."""
    assert _has_props(client, "/", href="/export")
