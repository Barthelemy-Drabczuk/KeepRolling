# ARCHITECTURE.md

Design record for Moodometer: component boundaries and the per-requirement
contracts implementations must satisfy. Owned by `design-specialist`; one
short entry per requirement, not a spec document. `CLAUDE.md` remains the
authority on how to run things; this file is about *what fits where*.

## Components

Moodometer is a single FastAPI process (`backend/app/app.py`) that wires
five backend modules with one responsibility each — `database.py` (engine,
`get_db` dependency, `init_db`), `models.py` (`UserModel` 1—N `MoodModel` /
`EntryModel`), `schemas.py` (Pydantic v2 request/response models),
`auth.py` (bcrypt + JWT, `get_current_active_user`), and `analytics.py`
(pure stat/query functions) — behind a flat REST surface at `/auth/...` and
`/users/{username}/...`, where every mutating endpoint runs
authenticate → `current_user.username == {username}` (403) → user lookup
(404) → child lookup scoped to the user (404) → mutate. As of the frontend
epic a sixth component joins it: **`backend/app/frontend/`**, a NiceGUI UI
package mounted onto that same FastAPI instance, which renders every page
in Python and is a **pure HTTP client of the REST API above** — it holds
the JWT in `app.storage.user` and calls the public endpoints, never
importing `models`, `database`, or `auth`. `app_new.py`, `index_new.html`,
and `User.py` are dead code and are not part of any boundary here.

### Boundaries (drift rules)

- `frontend/` must not import `models`, `database`, `auth`, or `analytics`.
  Authorization lives in `auth.py` only; the UI proves identity by sending
  the JWT to the API like any other client. The one sanctioned exception is
  re-deriving a *display label* locally (e.g. quadrant name from an
  `(energy, valence)` pair already fetched) instead of round-tripping.
- `app.py` keeps the REST routes; `frontend/` keeps the pages. No page
  handler gets a `Session`; no REST endpoint renders UI.
- Page registration must not touch the database at import time. Only
  request-handling code may. (Original rationale was NiceGUI's `user` test
  fixture re-executing `app.py` via `runpy` per test with no DB reachable;
  that fixture is now banned repo-wide — see FE-1's "Testing policy" — but
  the rule stands on its own: import-time DB access breaks `conftest.py`'s
  `get_db` override and the `init_db` no-op.)
- **No NiceGUI test fixtures.** `nicegui.testing.user` and
  `nicegui.testing.Screen` must not be used anywhere in this repo. See the
  FE-1 "Testing policy" subsection for the finding and what to do instead.

## Contracts

### FE-1 — Mount NiceGUI onto the FastAPI app, retire the vanilla-JS SPA

Lands in `app.py` (wiring) plus the new `backend/app/frontend/` package
(pages). New component, established here for every later FE item to extend.

**Page registration is function-call based, not import-time decorators.**
`frontend/__init__.py` exposes:

```python
def create_pages() -> None:
    """Register every NiceGUI page. Called from app.py on each app build."""
```

with the `@ui.page(...)` definitions written *inside* `create_pages()` (or
inside per-module `create() -> None` functions it calls). Later FE items
add `frontend/auth.py`, `frontend/mood_pad.py`, etc., each with its own
`create() -> None`, invoked from `create_pages()`.

The original rationale for this shape was re-registration under the
NiceGUI `user` fixture's per-test `runpy` re-run of `app.py`. **That
rationale is obsolete** (the fixture is banned — see "Testing policy"
below), but the shape stays as implemented: explicit registration keeps
page setup out of import side effects, makes registration order visible at
the call site, and gives later FE items one obvious seam to hang a
`create()` on. Do not "simplify" it back to import-time decorators —
that would be a change with no benefit and would reintroduce the
import-side-effect coupling the boundary rules above forbid.

For FE-1 the single placeholder page lives in `create_pages()` itself:

```python
@ui.page("/")
def index() -> None:
    ui.label("Moodometer")
```

`app.py` gains, **as the last statements in the module** (after every
`@app.<method>` route is registered) — ordering is load-bearing:

```python
STORAGE_SECRET = os.getenv("NICEGUI_STORAGE_SECRET", "change-me-in-production")

create_pages()
ui.run_with(app, mount_path="/", storage_secret=STORAGE_SECRET)
```

Decisions baked into that call:

- **`mount_path="/"`** — NiceGUI owns the site root, as `index.html` did.
  Safe because Starlette dispatches to the first matching entry of
  `app.routes` in registration order: the explicit `/auth/...`,
  `/users/...` routes and FastAPI's own `/docs`, `/redoc`, `/openapi.json`
  (registered in `FastAPI.__init__`) all precede this catch-all mount.
  Consequence to accept: unmatched paths now render NiceGUI's 404 rather
  than FastAPI's JSON `{"detail": "Not Found"}`. **Verify at
  implementation time, not on faith** — and **it since has been**; see the
  traceability paragraph ending this entry for exactly what was checked
  against a live dev server. (Original acceptance note: full suite green
  plus a manual `GET /docs` and one `GET /users/{u}/moods` against the dev
  server.)
- **`storage_secret` wired now**, from a *separate* `NICEGUI_STORAGE_SECRET`
  env var following `auth.py`'s `os.getenv(..., placeholder)` pattern —
  even though nothing uses `app.storage.user` until FE-3. Deliberately not
  reused from `SECRET_KEY`: signing session cookies and signing JWTs are
  different purposes and should not share a key. Doing it now means FE-3
  does not have to reopen this wiring. Needs a `.env`/docs mention in the
  FE docs-sync item.

**Removed by FE-1:** the `app.mount("/static", StaticFiles(...))` line and
its `StaticFiles` import, the `GET /` `read_root` route and its
`FileResponse` import, and the files `backend/app/index.html`,
`backend/app/index_new.html`, `backend/app/static/app.js`,
`backend/app/static/style.css` (which empties `static/`). Confirmed by
grep: the only remaining `/static` or `index.html` references are in
`app_new.py` (dead), and in `README.md` / `CLAUDE.md` prose (docs-sync).

#### Testing policy for the whole FE epic (FE-1 … FE-10)

Recorded at implementation time of FE-1, after the finding below cost a
full-suite breakage. **This section governs every later FE item; it is not
FE-1 trivia.**

**Finding: NiceGUI's own test fixtures are incompatible with this repo's
test architecture.** `nicegui.testing.user` (and `Screen`, which shares the
mechanism) works by re-executing `main_file` — `app.py` — fresh via
`runpy.run_path()` for every test, wrapped in `nicegui_reset_globals()`.
That reset clears NiceGUI's **process-global** "has `ui.run`/`ui.run_with`
been called" state after each such test. But `tests/conftest.py`'s
`client`/`TestClient` fixture — which all 242 pre-existing tests use —
reuses **one shared, already-imported `app_module.app` instance** for the
entire session and never re-runs `ui.run_with()`. So the first
`user`-fixture test's teardown invalidates the NiceGUI wiring on the shared
app, and every `client` test that runs afterwards in the same pytest
process dies with `RuntimeError: You must call ui.run()...`. Observed
concretely: 82 errors across every test file sorting alphabetically after
`test_frontend.py`. The fixtures pass in isolation, which is exactly what
makes this trap worth writing down — an isolated-file spike does **not**
clear them.

Consequently:

- **Do not use `nicegui.testing.user` or `nicegui.testing.Screen` anywhere
  in this repo**, in any FE item, even "just for one test", even in a file
  that appears to run last. Alphabetical ordering is not a contract, and
  the failure mode is spooky action on unrelated files. Correspondingly, do
  not add `pytest_plugins = ["nicegui.testing.user_plugin"]` to
  `conftest.py`, nor `main_file`/`asyncio_mode` to `pytest.ini` — all of
  that was reverted and none of it is used.
- **Default for FE tests: the ordinary `client`/`TestClient` fixture.**
  Assert on response status code and on rendered-HTML text content. This is
  not limited to the static shell: NiceGUI injects the page's *initial
  rendered content* into the server-delivered HTML, so a `ui.label(...)`'s
  text is present in `client.get("/").text` and asserting on it is
  meaningful, not vacuous. Verified empirically for FE-1. Page titles,
  labels, headings, button captions, link targets, and which page a route
  serves are all reachable this way — as is anything the page renders from
  an initial API read.
- **Live client-side interaction stays manual-verification-only**, via the
  dev server (`cd backend/app && uvicorn app:app --reload`), per the FE
  plan's original fallback. This applies specifically to **FE-4** (pointer
  dragging on the `ui.interactive_image` mood pad, marker tracking the
  cursor, coordinate mapping under real mouse events), **FE-5** (the
  confirm-action click path from pad to `POST /moods`, insofar as it needs
  a real click rather than a direct API assertion), and **FE-6** (arrow-key
  nudging and Enter-to-submit keyboard handling). Those behaviors are
  browser-runtime, not server-rendered, so no `TestClient` assertion
  reaches them — and the answer is a manual smoke check plus a note in the
  commit, **not** reaching for the `user`/`Screen` fixtures. When FE-4/5/6
  contracts are written, split each into a server-observable part (test it
  with `client`) and a browser-only part (manual), and say which is which.
- Whatever an FE item's UI does, the REST endpoint underneath it is already
  covered by ordinary API tests. Prefer pushing a behavior's assertion down
  to that layer over trying to observe it through the UI.

**Traceability:** FE-1 → `frontend.create_pages()` + `ui.run_with(app,
mount_path="/", storage_secret=...)` in `app.py`; verified by
`backend/app/tests/test_frontend.py::test_root_page_serves_nicegui_placeholder`
(plain `client` fixture; 243 passed with no cross-file pollution). Runtime
verification of the `mount_path="/"` decision was done against a real
`uvicorn` dev server, not only the test client: `GET /` → 200 (NiceGUI
page), `GET /docs` → 200 (Swagger UI unshadowed), and `/openapi.json` still
lists every `/users/...` REST path — so the catch-all mount demonstrably
shadows nothing. Page title set via `@ui.page("/", title="Moodometer")`
(NiceGUI otherwise defaults it to "NiceGUI").

### FE-2 — Quadrant colour palette in the Quasar brand config

No new component. The palette is presentation state owned by
`frontend/`, so it lands there rather than in `app.py`: `frontend/__init__.py`
gains a second exported function alongside `create_pages()`, and `app.py`
only calls it. Three reasons this is not just taste. (1) `create_pages()`
is contracted as *"Register every NiceGUI page"* and is the seam FE-4…FE-10
hang their per-module `create()` calls on; folding global config into it
blurs that seam for every later item. (2) The colour names are consumed
from inside `frontend/` — FE-3's primary buttons, FE-4's quadrant fills,
FE-9's chart series — so definition and use stay in one module. (3) In
`app.py` the name `app` is already the `FastAPI` instance, so `app.colors()`
there would need `from nicegui import app as nicegui_app` and would read
like configuring the FastAPI app; inside `frontend/__init__.py` there is no
such collision. What stays in `app.py` is *mounting* — `ui.run_with(app,
...)` genuinely needs the FastAPI instance and the storage secret; a colour
palette does not.

```python
# frontend/__init__.py — imports become `from nicegui import app, ui`

def configure_theme() -> None:
    """Bind the circumplex quadrant colours into Quasar's brand palette."""
    app.colors(
        high_energy_unpleasant="#783020",
        high_energy_pleasant="#e0c080",
        low_energy_unpleasant="#98a8c0",
        low_energy_pleasant="#a0a888",
    )
```

Called from `app.py`'s trailing frontend block, before page registration, so
the final ordering is theme → pages → mount:

```python
frontend.configure_theme()
frontend.create_pages()
ui.run_with(app, mount_path="/", storage_secret=STORAGE_SECRET)
```

Custom (non-Quasar) keyword arguments to `app.colors()` are carried through
to the rendered page as entries of `vue_config`'s `brand` object, with `_`
normalized to `-` in the key — so `high_energy_unpleasant=...` surfaces as
`"high-energy-unpleasant"`, which is the form the tests assert on. Verified
empirically by `requirement-specialist` when the tests were written (see the
module docstring of `tests/test_frontend.py`); no need to re-check. Note for
FE-3/FE-4/FE-9: they reference these colours by name; which spelling Quasar
wants at the *use* site (`ui.button(color=...)` etc.) is theirs to settle,
not settled here.

**Traceability:** FE-2 → `frontend.configure_theme()` in
`backend/app/frontend/__init__.py`, invoked from `app.py`'s frontend block;
verified by `backend/app/tests/test_frontend.py`'s four
`test_brand_palette_defines_*` tests (plain `client` fixture, per the FE-1
testing policy — the palette is server-rendered into `GET /`, so no NiceGUI
fixture is needed or permitted).

### FE-3a — `/login` and `/register` page shape

No new component. This is the first of the per-module page files FE-1's
entry anticipated: new file **`backend/app/frontend/auth.py`** with

```python
def create() -> None:
    """Register the /login and /register pages."""
```

`frontend/__init__.py` imports it (`from . import auth as auth_pages` — a
relative import, aliased so no reader confuses it with the top-level
backend `auth.py`; they are different module paths and neither shadows the
other, and the boundary rules forbid `frontend/` importing the backend one
anyway) and calls `auth_pages.create()` from `create_pages()`. `/` stays
inline in `create_pages()`; nothing else in `__init__.py` changes.

The two pages, literally — the calls are the contract, since the tests
assert on NiceGUI's server-rendered per-element `props` objects:

```python
@ui.page("/login")
def login() -> None:
    ui.input("Username")
    ui.input("Password", password=True)
    ui.button("Log in", color="high-energy-pleasant")
    ui.link("Register", "/register")


@ui.page("/register")
def register() -> None:
    ui.input("Username")
    ui.input("Password", password=True)
    ui.button("Register", color="high-energy-pleasant")
    ui.link("Log in", "/login")
```

Four things in that are load-bearing rather than taste:

- **The colour name must be hyphenated at the use site.** Settling the
  question FE-2 left open: `app.colors()` normalizes `_` → `-` and adds the
  custom names to NiceGUI's module-global `QUASAR_COLORS`
  (`nicegui/app/app.py:373`, 3.16.0 — read, not recalled). `ui.button`'s
  `color=` only becomes the element's **`color` prop** for names in that
  set; anything else silently becomes an inline
  `style="background-color: ..."` instead. So `color="high_energy_pleasant"`
  would render nothing the test can see, and no error either.
- **`configure_theme()` must have run before a page renders**, for the same
  reason. It does: `app.py` calls it at import, and page bodies build
  elements per request — one more reason element construction stays out of
  import time.
- **Cross-navigation must be `ui.link`**, which is what puts `href` in
  props. A `ui.button(on_click=lambda: ui.navigate.to(...))` renders no
  `href`, fails the test, and would only work over the websocket, which is
  FE-3b's half.
- **No unused local handles** (`username = ui.input(...)`) — ruff `F841`.
  FE-3b introduces the handles together with the handler that reads them.

Link *caption* is not pinned: `ui.link`'s text renders under the element's
`text` key, not `props`, so the tests assert `href` only. "Register" /
"Log in" above are for consistency; nothing depends on them.

Out of scope for FE-3a, deliberately: form submission, `POST /auth/...`,
`app.storage.user`, post-login navigation (all FE-3b, manual-verified per
the FE-1 testing policy), plus nav layout, page titles, and any styling
beyond the button colour. No auth guard on either route in either
direction.

**Traceability:** FE-3a → `frontend.auth.create()` in
`backend/app/frontend/auth.py`, invoked from `frontend.create_pages()`;
verified by the twelve `test_login_page_*` / `test_register_page_*` tests in
`backend/app/tests/test_frontend.py` (plain `client` fixture).
