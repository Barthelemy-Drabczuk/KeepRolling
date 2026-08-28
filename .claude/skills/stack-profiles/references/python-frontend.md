# Python / NiceGUI frontend profile

Covers `src/frontend/` — the NiceGUI pages mounted onto the same
FastAPI app the `python` profile's REST endpoints live in, imported via
an explicit `sys.path` insert in `app.py` since `src/frontend/` is a
sibling of `src/backend/`, not a subdirectory of it. Same language, same
test runner, but "red"/"verify"/"green" mean something importantly
narrower here: most of what a page *does* at runtime is not observable
through `pytest` at all, and one specific NiceGUI testing mechanism is
banned outright. Read this whole profile before writing a frontend
test, not just the commands section — the caution below is the part
that actually matters.

**Location & naming:** despite `src/frontend/` living outside
`src/backend/`, its tests live with the backend's, under
`src/backend/app/tests/` — no separate test directory for the frontend
package (`src/backend/app/pytest.ini`'s `pythonpath` entry is what makes
`from frontend.history import ...` resolve from there). Page-shape
assertions mostly live in `src/backend/app/tests/test_frontend.py`; a
page with its own pure helper functions (a coordinate mapper, a
classifier, an options builder for a chart) gets its own
`test_<page>.py` or `test_<page>_page.py` file for those, following
whatever the sibling page files already established (e.g.
`test_history.py`, `test_analytics_page.py` — the `_page` suffix exists
specifically to avoid colliding with a same-named backend test module).

**Red confirmation:** run `pytest` from `src/backend/app/`, same command
and cwd requirement as the `python` profile (bare imports). The same
rule about a collection error not being a valid red state applies, with
one frontend-specific trap: a `client.get(...)` against a route that
renders fine server-side but crashes on some *authenticated* branch (one
that needs `app.storage.user` seeded) will not fail the way you expect —
`app.storage.user` cannot be seeded over HTTP at all, so that whole
branch is outside what a `pytest` red state can express in the first
place. See "Cautions" below before assuming a red test proves what it
looks like it proves.

**Verify commands, in order:** identical to the `python` profile —
`ruff format --check .` and `ruff check .` from the repo root, `pytest`
from `src/backend/app/`, full suite. `src/frontend/`'s files are covered
by the same root `pyproject.toml` `[tool.ruff]` config; nothing about
them needs a different lint/format invocation.

**Cautions, unique to this stack:**

- **`nicegui.testing.user` and `nicegui.testing.Screen` are banned
  outright, anywhere in this repo.** They reset NiceGUI's process-global
  `ui.run`/`ui.run_with` state on teardown, which corrupts the shared
  `client`/`TestClient` fixture every other test in the same pytest
  process depends on — observed concretely as 82 errors across every
  test file sorting alphabetically after the one that used them. This
  fails in the full suite, not in an isolated one-file spike, which is
  exactly what makes it easy to miss. Do not add
  `pytest_plugins = ["nicegui.testing.user_plugin"]` to `conftest.py` or
  `main_file`/`asyncio_mode` to `pytest.ini` to work around it — use the
  plain `client` fixture instead, per the next point.
- **Default to the ordinary `client`/`TestClient` fixture, and it proves
  more than it looks like it does.** NiceGUI injects a page's *initial
  server-rendered content* into the HTML response, so a `ui.label`'s
  text, a button's caption/colour prop, a link's `href`, and anything a
  page renders from an initial (pre-interaction) API read are all
  genuinely assertable via `client.get(path).text` — not a vacuous
  smoke check. Prefer this over reaching for a browser-level test.
- **Live client-side interaction is manual-verification-only, not
  something to route around with a workaround fixture.** Pointer drags,
  real keyboard events, and anything that only happens after a
  websocket round-trip are browser-runtime and unreachable from
  `TestClient`. Split a page's contract three ways before writing tests
  for it: pure arithmetic/logic (a plain unit test, no fixture needed),
  the initial render (the `client` fixture, per the point above), and
  live interaction (manual, via `cd src/backend/app && uvicorn app:app
  --reload`, recorded in the commit message — not "it's interactive, so
  it's all manual").
- **Push an assertion down to the REST layer instead of trying to
  observe it through the UI, whenever the same behavior is already
  covered there.** The endpoint underneath a page's fetch already has
  its own `python`-profile tests; re-asserting the same response shape
  through a page's rendered HTML is redundant and more fragile.
- **`app.storage.user` cannot be seeded over HTTP.** Any branch that
  depends on a logged-in session (a populated chart, a personalized
  empty state distinct from the logged-out one, a 401-vs-other-failure
  distinction behind auth) is manual-verification-only for the same
  reason as live interaction above — there is no fixture-level trick
  that reaches it, so don't go looking for one.
