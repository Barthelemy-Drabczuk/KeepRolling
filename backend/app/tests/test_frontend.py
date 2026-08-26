"""Tests for the NiceGUI frontend mounted onto the FastAPI app (FE-1, FE-2, FE-3a)."""

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
