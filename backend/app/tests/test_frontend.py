"""Tests for the NiceGUI frontend mounted onto the FastAPI app (FE-1, FE-2, FE-3a, FE-4, FE-5)."""

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
