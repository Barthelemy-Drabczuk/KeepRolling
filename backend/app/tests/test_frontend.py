"""Tests for the NiceGUI frontend mounted onto the FastAPI app (FE-1, FE-2)."""

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
