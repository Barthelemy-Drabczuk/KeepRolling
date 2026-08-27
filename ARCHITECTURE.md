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
- **`ui.navigate.to()` is navigation, never an auth guard.** It runs after
  the page body has already rendered and been delivered, so any content the
  page built is on the client's screen before the redirect fires. It is
  correct for *post-action* navigation between pages that are themselves
  public (FE-3b's "go to `/` after login", "go to `/login` after register" —
  nothing is being withheld). The first item that must actually withhold
  content from an unauthenticated visitor must instead return a
  `starlette.responses.RedirectResponse` from the page function *before*
  building any element. See FE-3b's forward pointers.

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
  **Amended by FE-4:** the carve-out is narrower than the FE-4 sketch above
  implies. It covers *real mouse events*, not arithmetic and not the initial
  render. FE-4's entry below splits it three ways — pure arithmetic
  (`pixel_to_mood`, plain unit test), initial render (the pad's `size` /
  `events` / SVG `content` are all server-rendered props, `client` fixture),
  and only the live drag (manual). Later items should look for the same
  three-way split rather than assuming "it's interactive" means "it's
  manual".
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

### FE-3b — Form submission: login/register call the REST API

Lands in the existing `backend/app/frontend/auth.py` (the two page
functions FE-3a created gain local input handles and an async click
handler), plus **one new small module, `backend/app/frontend/api.py`**,
which owns the HTTP transport. No change to `frontend/__init__.py`,
`app.py`, or `pyproject.toml` (`httpx>=0.27.0` is already a runtime
dependency).

#### Transport decision: in-process ASGI, not a network round-trip

`frontend/` calls its own co-hosted REST API through
`httpx.AsyncClient(transport=httpx.ASGITransport(app=<the FastAPI app>))`
— no socket, no configurable base URL, no host/port to get wrong behind a
proxy or in Docker. This **does not weaken the boundary**: the call still
goes through the public REST interface (routing, Pydantic validation,
`get_current_active_user`, the whole middleware stack), it just skips the
loopback socket. It is also the transport `nicegui.testing.user_plugin`
uses internally in this same dependency stack. Rejected alternative: a real
request to the app's own host:port, which buys nothing and adds
connection-refused/timeout/proxy failure modes that only appear in some
deployments.

**The FastAPI instance must be imported lazily, inside the call.**
`app.py` does `import frontend` at module level (line 17), *before*
`app = FastAPI(...)` exists, and `frontend/__init__.py` imports
`frontend.auth`. A top-level `import app` anywhere under `frontend/` is
therefore a circular import that fails at startup. This is the whole
reason `api.py` exists as its own module rather than being three lines
inlined into `auth.py`: the trap gets explained once, and FE-5/7/8/9/10 —
which all need the same client, plus an `Authorization` header — extend
one function instead of copy-pasting the transport five times.

```python
# backend/app/frontend/api.py
import httpx

BASE_URL = "http://moodometer.internal"  # ASGITransport ignores the host;
                                         # httpx just requires an absolute URL


def client() -> httpx.AsyncClient:
    """An httpx client that dispatches straight into the FastAPI app."""
    # Imported here, not at module scope: app.py imports `frontend` before it
    # defines `app`, so a top-level `import app` is a circular import.
    import app as backend

    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=backend.app, raise_app_exceptions=False),
        base_url=BASE_URL,
    )
```

`raise_app_exceptions=False` is load-bearing, not a default being restated.
With httpx's default (`True`), an *unhandled* server-side exception — a DB
outage, say — propagates out of `await http.post(...)` into the click
handler instead of arriving as a response, so a status-code-only error
branch would miss it entirely and the traceback would surface to the user.
With `False`, httpx synthesizes a `500` response (verified by reading
`httpx/_transports/asgi.py:169-187` in `.pixi/envs/default`, not recalled),
which falls into the generic-message branch below; Starlette's
`ServerErrorMiddleware` still logs the traceback server-side. `HTTPException`
raised by the endpoints (401, 400) is *handled* by FastAPI either way and
always arrives as a normal response.

#### The click handlers must be `async` and must `await` the call

`ui.button(on_click=...)` accepts a coroutine function. A **synchronous**
httpx call inside the handler would block NiceGUI's single event loop for
its whole duration — freezing every connected client's UI, not just the one
that pressed the button. Both handlers below are `async def` and `await`
every HTTP call. (Related and pre-existing, not FE-3b's to fix: `POST
/auth/login` is an `async def` endpoint that runs bcrypt verification
synchronously, so it occupies the loop for ~100ms regardless of transport.)

#### `frontend/auth.py`, literally

`from nicegui import app, ui` (the module currently imports `ui` only) plus
`from . import api`. Note there is no name collision here: the backend
FastAPI instance is never bound in this module — `api.client()` reaches it.

```python
@ui.page("/login")
def login() -> None:
    username = ui.input("Username")
    password = ui.input("Password", password=True)

    async def submit() -> None:
        async with api.client() as http:
            response = await http.post(
                "/auth/login",
                data={"username": username.value, "password": password.value},
            )
        if response.status_code == 200:
            app.storage.user["token"] = response.json()["access_token"]
            app.storage.user["username"] = username.value
            ui.navigate.to("/")
        elif response.status_code == 401:
            ui.notify("Incorrect username or password")
        else:
            ui.notify("Could not complete the request.")

    ui.button("Log in", color="high-energy-pleasant", on_click=submit)
    ui.link("Register", "/register")


@ui.page("/register")
def register() -> None:
    username = ui.input(
        "Username",
        validation={"Username must be 3-50 characters": lambda v: 3 <= len(v or "") <= 50},
    )
    password = ui.input(
        "Password",
        password=True,
        validation={"Password must be at least 8 characters": lambda v: len(v or "") >= 8},
    )

    async def submit() -> None:
        username_ok = username.validate()
        password_ok = password.validate()
        if not (username_ok and password_ok):
            return
        async with api.client() as http:
            response = await http.post(
                "/users",
                json={"username": username.value, "password": password.value},
            )
        if response.status_code == 201:
            ui.navigate.to("/login")
        elif response.status_code == 400:
            ui.notify("Username already registered")
        else:
            ui.notify("Could not complete the request.")

    ui.button("Register", color="high-energy-pleasant", on_click=submit)
    ui.link("Log in", "/login")
```

Load-bearing details in that:

- **`data=` for login, `json=` for register.** `POST /auth/login` takes an
  `OAuth2PasswordRequestForm` — form-encoded. `POST /users` takes a
  `UserCreate` Pydantic body — JSON. Swapping them yields a `422`, which
  lands in the generic branch and looks exactly like a server fault, hiding
  the actual bug.
- **Status code first, body never.** Success (200 / 201) → the specific
  error (401 / 400, verbatim strings from the endpoints' own `detail`) →
  `else:` generic. The `else` catches 422, every 5xx, and the synthesized
  500 above. The raw response body must never reach `ui.notify`:
  REQ-USER-1's 422 detail echoes the submitted password back in `input`.
- **Client-side length validation lives on the register `ui.input`s**, as
  NiceGUI's `validation=` dict (`message -> predicate`), giving inline field
  errors as the user types. It does **not** gate the button on its own —
  `ValidationElement` auto-validates on value change but nothing blocks a
  click — so `submit()` re-checks with explicit `.validate()` calls and
  returns early. Both are evaluated before the `and` on purpose: `if not
  (username.validate() and password.validate())` would short-circuit and
  leave the password field's error message unset. Bounds mirror
  `schemas.UserCreate` (username 3-50, password ≥8). Login gets no such
  validation — a wrong-length password there is simply wrong credentials,
  and the 401 path already covers it.
- Adding `validation=` adds an `error` prop to those elements. FE-3a's
  tests match props as a subset (`_has_props`), so they stay green.

Out of scope, deliberately: logout, any `Authorization` header, any auth
guard on any page, "already logged in" redirects, disabling the button
while the request is in flight.

#### Forward pointers (findings later items would otherwise rediscover)

- **`token_type` is dropped.** Login stores the bare `access_token` string
  in `app.storage.user["token"]`; the response's `"token_type": "bearer"`
  is discarded. Whoever first builds an `Authorization` header (FE-5
  onward) must write the prefix themselves —
  `{"Authorization": f"Bearer {app.storage.user['token']}"}` — and must not
  assume the stored value already carries it.
- **`ui.navigate.to` is not a guard.** Its two uses here are correct
  because `/` and `/login` are both genuinely public in FE-3b; nothing is
  withheld, it is just post-action navigation. The first item that needs to
  *hide* a page from an unauthenticated visitor must return a
  `RedirectResponse` from the page body before constructing any element —
  `ui.navigate.to` fires after the page has rendered and shipped, so the
  protected content is already on screen. See the drift rule added to
  "Boundaries" above.

**Traceability:** FE-3b → `frontend.api.client()` in
`backend/app/frontend/api.py` + the `submit()` click handlers inside
`frontend.auth.create()`'s `login()` / `register()` pages in
`backend/app/frontend/auth.py`. **No pytest test**: the behavior is
dispatched over NiceGUI's websocket from click handlers and is unreachable
through the `client`/`TestClient` fixture, per the FE-1 Testing policy's
manual-verification carve-out. Verified instead by the four enumerated
manual acceptance steps in `TASKS.md`'s FE-3b row — login-success (incl.
inspecting `backend/app/.nicegui/storage-user-*.json` for `token` +
`username`), register-success, login-401, register-400 — all four required,
and the result recorded in the commit message.

### FE-4 — The mood pad at `/`

No new component. New file **`backend/app/frontend/mood_pad.py`**, the
second per-module page file after FE-3a's `frontend/auth.py`, with the same
`create() -> None` shape.

**The `@ui.page("/", title="Moodometer")` definition moves out of
`create_pages()` into `mood_pad.py` entirely** — it is not "the body gets
replaced in place". Rationale: FE-3a established that a page's decorator
and its body live together in the page module; `/` was only left inline
because FE-1 had nothing else to put there. After FE-4, `create_pages()`
contains no `@ui.page` block at all and is purely a registration list,
which is the seam FE-5…FE-10 hang on:

```python
def create_pages() -> None:
    """Register every NiceGUI page."""
    mood_pad.create()
    auth_pages.create()
```

`frontend/__init__.py` gains `from . import mood_pad` alongside
`from . import auth as auth_pages`; the `ui` import there becomes unused
once the inline page goes, so drop it (ruff `F401`) and keep
`from nicegui import app` for `configure_theme()`. `title="Moodometer"` is
load-bearing: it is the only thing keeping FE-1's
`test_root_page_serves_nicegui_placeholder` green once the
`ui.label("Moodometer")` placeholder is deleted. **No auth guard on `/`**,
consistent with FE-3a — so FE-3b's `RedirectResponse`-vs-`ui.navigate.to`
forward pointer is *not* triggered by this item and stays open for whichever
item first withholds content.

#### The pure function (the one unit-tested thing)

```python
def pixel_to_mood(x: float, y: float, width: float, height: float) -> tuple[float, float]:
    """Map a pad pixel to a clamped ``(valence, energy)`` pair."""
    valence = min(1.0, max(-1.0, x / width * 2 - 1))
    energy = min(1.0, max(-1.0, 1 - y / height * 2))
    return valence, energy
```

**The return order is `(valence, energy)` — the opposite of how the rest of
this codebase orders the pair** (`MoodModel`, `schemas`, `analytics`, and
FE-4's own readout label all say energy first). This is pinned by
`tests/test_mood_pad.py`, which reads corner `(0, 0)` as `(-1.0, 1.0)`; it
must not be "fixed" by making the implementation disagree with the tests.
Every call site therefore unpacks `valence, energy = pixel_to_mood(...)` and
must re-order when handing the pair to anything else. A module-private
inverse exists for the marker, so the clamp is not re-implemented inline:

```python
def _mood_to_pixel(valence: float, energy: float, width: float, height: float) -> tuple[float, float]:
    return (valence + 1) / 2 * width, (1 - energy) / 2 * height
```

#### The pad element and the SVG, literally

`PAD_WIDTH = PAD_HEIGHT = 400`, `QUADRANT = 200`. The element:

```python
pad = ui.interactive_image(
    size=(PAD_WIDTH, PAD_HEIGHT),          # no `src`: source-less is legal and needs no asset
    events=["mousedown", "mousemove", "mouseup"],
    cross=False,
    content=_pad_svg(*_mood_to_pixel(0.0, 0.0, PAD_WIDTH, PAD_HEIGHT)),
    on_mouse=handle_mouse,
)
ui.label(_readout(0.0, 0.0))               # "Energy: 0.00 · Valence: 0.00"
```

`_pad_svg(marker_x, marker_y) -> str` builds the whole overlay so FE-5/FE-6
re-render it by assigning `pad.content = _pad_svg(...)` rather than
string-patching. It returns `"".join(parts)` of these elements, in this
order. The four rects are exactly the quadrants (the tests compare
`(x, y, width, height)` to `(left, top, 200.0, 200.0)` for equality, so
these are not approximate):

| slot | fill | x | y | w | h |
|---|---|---|---|---|---|
| top-left | `var(--q-high-energy-unpleasant)` | 0 | 0 | 200 | 200 |
| top-right | `var(--q-high-energy-pleasant)` | 200 | 0 | 200 | 200 |
| bottom-left | `var(--q-low-energy-unpleasant)` | 0 | 200 | 200 | 200 |
| bottom-right | `var(--q-low-energy-pleasant)` | 200 | 200 | 200 | 200 |

Then seven `<text x=".." y=".." text-anchor="middle" font-family="sans-serif"
font-size="14" fill="..">CAPTION</text>`. The tests read the `x`/`y`
*attributes* and require `left <= x <= left+200` and `top <= y <= top+200`,
so the anchor point alone is what is checked — but these coordinates are
also chosen so the *rendered* string stays inside its quadrant at 14px
(the longest, "We are so fucking back", is ~155px wide and is nudged
inboard to x=290 for that reason, breaking the otherwise-symmetric
placement on purpose). Single-caption quadrants sit at the quadrant centre;
multi-caption quadrants stack along the quadrant's diagonal, **most-central
first**, matching the requirement's stated reading order — distance from the
pad centre (200, 200) increases down each group:

| caption | quadrant | x | y | dist. from centre |
|---|---|---|---|---|
| Fuck it we ball | top-left | 100 | 100 | 141 |
| We are so fucking back | top-right | 290 | 130 | 114 |
| Let's fucking goooo | top-right | 320 | 70 | 177 |
| It is what it is | bottom-left | 130 | 270 | 99 |
| It's so over | bottom-left | 100 | 300 | 141 |
| Mom would be sad | bottom-left | 70 | 330 | 184 |
| We vibing | bottom-right | 300 | 300 | 141 |

Caption `fill` is `#ffffff` in the top-left quadrant only (over `#783020`)
and `#202020` in the other three; those are plain hex, not palette
references, because they are contrast against the palette rather than the
palette itself. Only `<rect>`s may carry a `var(--q-...)` fill — the tests
assert *exactly one* rect per slot colour.

Finally the marker, two concentric rings so it stays visible over all four
quadrant colours (it sits where they meet). Coordinates are formatted
`:.1f`, which keeps the centre at `"200.0"` — parsed by the test as `200.0`
— and stops drag updates emitting 17-digit floats:

```
<circle cx="200.0" cy="200.0" r="9" fill="none" stroke="#202020" stroke-width="4" />
<circle cx="200.0" cy="200.0" r="9" fill="none" stroke="#ffffff" stroke-width="2" />
```

Two hard constraints on anything ever added to this string, both from
reading NiceGUI 3.16.0 rather than guessing:

- **No `{` or `}`, anywhere** — no inline `style="..."`, no CSS block.
  `content` is serialized into the same HTML document that
  `tests/test_frontend.py`'s brace-depth `_rendered_props` helper and the
  `const vue_config = (\{.*?\});` regex scan, and a brace inside the SVG
  mis-parses them. (`var(--q-...)` uses parentheses, so the palette
  reference is safe.)
- **No backtick and no `${`** — the served page embeds `content` inside a JS
  ``String.raw`...` `` template literal. The seven captions contain neither;
  apostrophes ("Let's", "It's") are fine and must be written literally, not
  as `&#39;`.

#### Colour form: `var(--q-{slot})` is confirmed, not a manual check

FE-2 deferred "which spelling at the use site"; FE-3a settled it for
`ui.button(color=...)` (bare hyphenated name); FE-4 settles it for raw SVG.
The answer is `fill="var(--q-high-energy-unpleasant)"` — hyphenated,
because `nicegui/static/nicegui.js:59-66` does
`document.body.style.setProperty("--q-" + color.replaceAll("_", "-"), ...)`,
so the property that actually exists is `--q-high-energy-unpleasant` and the
pad's `<svg>`, being a descendant of `<body>`, inherits it.

**The DOMPurify question the FE-4 investigation flagged is resolved in the
affirmative — do not re-raise it as a manual check.** Read from the bundled
`nicegui/static/dompurify.mjs`: `fill` is *not* in `URI_SAFE_ATTRIBUTES`
(`["alt","class","for","id","label","name","pattern","placeholder","role",
"summary","title","value","style","xmlns"]`), so its value is tested against

```
IS_ALLOWED_URI = /^(?:(?:(?:f|ht)tps?|mailto|tel|callto|sms|cid|xmpp|matrix):|[^a-z]|[a-z+.\-]+(?:[^a-z+.\-:]|$))/i
```

and `var(--q-...)` matches the third alternative (`var` then `(`), so the
attribute is kept. `#202020`, `none`, `sans-serif` and `14` match too. Also
confirmed present in the `USE_PROFILES: {svg: true}` allow-lists: the tags
`rect`, `text`, `circle` and the attributes `fill`, `x`, `y`, `width`,
`height`, `cx`, `cy`, `r`, `stroke`, `stroke-width`, `font-family`,
`font-size`, `text-anchor`. One caveat, not a blocker: the value is
whitespace-stripped before that regex runs, so write `var(--q-x)` with no
spaces inside the parentheses. Cosmetic consequence worth knowing: the
palette is applied in a `mounted()` hook, so on the very first paint the
custom property may not yet resolve and `fill` falls back to black for a
frame.

#### The drag handler (browser-only half)

`events=[...]` with no handler would be dead, and `pixel_to_mood` would be
unused code, so FE-4 owns the handler — it is in scope, it is just not
pytest-reachable:

```python
def handle_mouse(event: events.MouseEventArguments) -> None:
    nonlocal dragging
    if event.type == "mousedown":
        dragging = True
    elif event.type == "mouseup":
        dragging = False
        return
    elif not dragging:
        return
    valence, energy = pixel_to_mood(event.image_x, event.image_y, PAD_WIDTH, PAD_HEIGHT)
    pad.content = _pad_svg(*_mood_to_pixel(valence, energy, PAD_WIDTH, PAD_HEIGHT))
```

Routing the marker back through `_mood_to_pixel(pixel_to_mood(...))` is
deliberate: it re-uses the one clamp, so a fast pointer whose `image_x`
overshoots `size` parks the marker on the edge instead of outside the pad.
`cross=False` is also deliberate and not just a default restated — `cross`
installs its own `mousemove` on the same `<img>` via a second object-syntax
`v-on`, which would collide with the `mousemove` in `events`.

**FE-4 updates the marker only; the readout label keeps its initial text.**
Live label updates and the confirm button are FE-5, per FE-4's row, and
FE-5 extends this same handler rather than adding a second one. `_readout(
energy, valence) -> f"Energy: {energy:.2f} · Valence: {valence:.2f}"` is
defined here (energy first, note the flip against `pixel_to_mood`'s return
order) so FE-5 has one place to call. The separator is U+00B7 MIDDLE DOT.

Out of scope, deliberately: `POST /moods`, any `Authorization` header, the
confirm button (FE-5); keyboard nudging (FE-6); any auth guard.

**Traceability:** FE-4 → `frontend.mood_pad.pixel_to_mood()` plus
`frontend.mood_pad.create()`'s `/` page in
`backend/app/frontend/mood_pad.py`, invoked from `frontend.create_pages()`
in `backend/app/frontend/__init__.py`. Verified by
`backend/app/tests/test_mood_pad.py` (11 unit tests on the mapping) and the
20 FE-4 tests in `backend/app/tests/test_frontend.py` (plain `client`
fixture, asserting the pad's `size` / `events` props and the four fills,
seven captions, marker centre and readout text inside the server-rendered
`content`). Drag-tracking and marker movement are the manual half per the
Testing policy above: with the dev server running from `backend/app/`, press
and drag on the pad and confirm the marker follows the cursor, stops at the
edge rather than leaving the pad, and does not move when the button is up —
record the result in the commit message.

### FE-5 — Confirm button: log the current mood via `POST /moods`

No new component and no new file. Everything lands inside
`backend/app/frontend/mood_pad.py`'s existing `create()` → `index()` page
closure (FE-4), which gains local state, one extra closure, a rewritten tail
of `handle_mouse`, an async click handler and the button itself. The module's
imports become `from nicegui import app, events, ui` plus `from . import api`
— the same pair `frontend/auth.py` already uses, and with the same absence of
a name collision (the backend FastAPI instance is never bound in this module;
`api.client()` reaches it lazily).

#### Decision 1 — current mood lives in two `nonlocal` floats beside `dragging`

`index()` gains `current_valence = 0.0` and `current_energy = 0.0` next to
FE-4's `dragging = False`, in that order (matching `pixel_to_mood`'s return
order, so `set_mood(*pixel_to_mood(...))` is safe). Rejected alternatives:
`app.storage.user` (this is per-tab UI state, not session state, and writing
it would put an unsubmitted mood in the cookie-backed store), a module-level
global (one process serves every client — it would leak one user's pad
position into another's), and `pad.content`-as-source-of-truth (re-parsing an
SVG string to recover two floats).

**State and rendering are updated together, through one closure**, so the
label, the marker and the two floats can never drift apart:

```python
def set_mood(valence: float, energy: float) -> None:
    nonlocal current_valence, current_energy
    current_valence, current_energy = valence, energy
    pad.content = _pad_svg(*_mood_to_pixel(valence, energy, PAD_WIDTH, PAD_HEIGHT))
    readout.text = _readout(energy, valence)
```

Note the argument-order flip on the last line: `_readout` is energy-first,
everything else here is valence-first (FE-4's entry explains why that
asymmetry exists and why it must not be "fixed"). `set_mood` has two call
sites in FE-5 — the drag handler and the post-201 reset — which is what earns
it over inlining. FE-6's arrow-key nudge will be the third.

FE-4's `handle_mouse` keeps its `dragging` guard verbatim; only its last two
lines change, from assigning `pad.content` directly to:

```python
            set_mood(*pixel_to_mood(event.image_x, event.image_y, PAD_WIDTH, PAD_HEIGHT))
```

That single line is what makes the readout live during a drag — the behavior
FE-4's row deferred here. `readout` therefore becomes a named handle
(`readout = ui.label(_readout(0.0, 0.0))`); it is read by `set_mood`, so no
ruff `F841`. The initial render still builds `content` / label text inline
from `_pad_svg`/`_readout`, because `set_mood` cannot run before `pad` and
`readout` exist.

#### Decision 2 — headers go on the request, `api.client()` is untouched

`api.client()` keeps its no-argument signature; the `Authorization` header is
passed to the individual call: `http.post(url, json=..., headers={...})`.
FE-5 is the only authenticated call site that exists today, and FE-7–10 are
undesigned — an `api.client(token=...)` parameter or an `api.auth_headers()`
helper now would be a guess at their shape. httpx merges per-request headers
over client defaults, so nothing is lost by deferring. **Forward pointer:**
when a third authenticated call site lands (FE-7/FE-8/FE-9), revisit this and
extract *then*, with three real usages to design against.

Per FE-3b's forward pointer, the stored token carries no `token_type` prefix,
so the handler writes `f"Bearer {token}"` itself.

#### The click handler, literally

```python
async def log_mood() -> None:
    username = app.storage.user.get("username")
    token = app.storage.user.get("token")
    if not username or not token:
        # Nothing stored: same user-visible outcome as the API's 401, but
        # short-circuited here because f"/users/{None}/moods" would be a
        # wrong URL and f"/users//moods" matches no route (Starlette's
        # {username} is [^/]+), so either would 404 into the generic branch.
        ui.notify("Please log in to record a mood.")
        ui.navigate.to("/login")
        return
    async with api.client() as http:
        response = await http.post(
            f"/users/{username}/moods",
            json={"energy": current_energy, "valence": current_valence},
            headers={"Authorization": f"Bearer {token}"},
        )
    if response.status_code == 201:
        ui.notify("Mood logged!")
        set_mood(0.0, 0.0)
    elif response.status_code == 401:
        ui.notify("Please log in to record a mood.")
        ui.navigate.to("/login")
    else:
        ui.notify("Could not complete the request.")


ui.button("Log this mood", color="high-energy-pleasant", on_click=log_mood)
```

placed immediately after `readout = ui.label(...)`, so it renders below the
readout as the row specifies. Load-bearing details:

- **`async def` + `await`**, per FE-3b: a synchronous HTTP call here would
  block the shared event loop and freeze every connected client.
- **No `enabled=`/`.disable()` anywhere.** NiceGUI writes
  `_props["disable"]` only when a `DisableableElement` is actually disabled,
  so an enabled button renders *no* `disable` key —
  `test_confirm_button_is_enabled_at_initial_render` asserts
  `props.get("disable") is not True`, which the plain constructor satisfies.
  Do not add `enabled=True` "for clarity"; it changes nothing and invites
  someone to later add a gate the requirement explicitly rejects.
- **`color="high-energy-pleasant"`, hyphenated**, per FE-3a: only names in
  NiceGUI's `QUASAR_COLORS` become the `color` prop; an underscored name
  silently degrades to an inline style and the test sees nothing.
- **Body is `{"energy", "valence"}` only** — no `notes`, no `timestamp`.
  `schemas.MoodCreate` makes both optional and REQ-MOOD-2 defaults the
  timestamp server-side. Energy first in the dict is cosmetic (JSON is
  unordered); the *values* being correctly paired is not — read them from
  `current_energy` / `current_valence` by name, never by unpacking a tuple.
- **Status code first, body never** (FE-3b's rule): 201 → 401 → `else`. The
  `else` absorbs 403, 422 and every 5xx, including the synthesized 500 that
  `api.client()`'s `raise_app_exceptions=False` produces.
- **The 401 branch's `ui.navigate.to("/login")` is post-action navigation,
  not an auth guard**, so it does not trigger FE-3b's `RedirectResponse`
  forward pointer. **`/` gains no auth guard in FE-5** — deliberate, and
  load-bearing: ~25 existing tests fetch `/` with a logged-out `client`
  fixture and expect 200.
- **Reset on success reuses `set_mood(0.0, 0.0)`**, which routes through
  `_mood_to_pixel`/`_pad_svg`/`_readout` — the marker and readout are never
  re-derived by hand or by string-patching `pad.content`.

The logged-out early return is FE-5's one design call beyond the row's text:
the row enumerates 201/401/else and names "missing token" as a 401 case, but
a *missing username* is a malformed URL rather than a 401 response, so it is
mapped onto the same user-visible outcome before the request is built.

Out of scope, deliberately: keyboard nudging and Enter-to-submit (FE-6);
`notes` on the mood; disabling the button while the request is in flight;
any auth guard on `/`; any change to `frontend/api.py`, `frontend/__init__.py`
or `app.py`.

**Traceability:** FE-5 → the `set_mood()` / `log_mood()` closures and the
`ui.button("Log this mood", ...)` inside `frontend.mood_pad.create()`'s
`index()` page in `backend/app/frontend/mood_pad.py`. Split in two, the same
shape as FE-4. **Automated slice** (plain `client` fixture, initial render
only): the three FE-5 tests in `backend/app/tests/test_frontend.py` —
`test_root_page_renders_the_confirm_button` (a rendered element is labelled
"Log this mood"), `test_confirm_button_uses_high_energy_pleasant` (that same
element carries `color="high-energy-pleasant"`), and
`test_confirm_button_is_enabled_at_initial_render` (it renders no
`disable: true`). Nothing else in FE-5 is TestClient-reachable, and the
endpoint underneath is already covered by `tests/test_moods.py`
(REQ-MOOD-1/2/5) — do not re-test it through the UI. **Manual slice** (dev
server from `backend/app/`, per the Testing policy; all six required, result
recorded in the commit message):

1. *Live readout* — drag on the pad and confirm the label under it updates
   continuously with the marker, ending on the values the marker's quadrant
   implies (top-right → both positive), and that it still reads
   `Energy: 0.00 · Valence: 0.00` before the first drag.
2. *Log success* — logged in, drag to a distinctive off-centre point, click
   "Log this mood", confirm the notification "Mood logged!" and that the
   marker and readout snap back to the centre / `0.00`.
3. *Persisted correctly* — after step 2, `GET /users/{username}/moods` (curl
   with the same bearer token, or `/docs`) returns a mood whose `energy` and
   `valence` match the readout as it stood at click time, **not** swapped.
   This is the one step that catches a valence/energy flip, which no other
   check here would.
4. *Logged out* — in a fresh private window (no `app.storage.user` entries),
   click the button without logging in and confirm the notification "Please
   log in to record a mood." and navigation to `/login`.
5. *Expired/invalid token* — edit `token` in
   `backend/app/.nicegui/storage-user-*.json` to a garbage string, reload
   `/`, click, and confirm the same 401 notification and redirect (this
   exercises the real response branch, where step 4 exercises the
   short-circuit).
6. *Generic failure* — force a non-401 failure (e.g. set `username` in that
   same storage file to another existing user, making the API answer 403) and
   confirm the notification is exactly "Could not complete the request." with
   no response body, no traceback, and no navigation.

### FE-6a — Keyboard focus and arrow-key nudging on the pad

No new component, no new file, no new dependency. Everything lands inside
`backend/app/frontend/mood_pad.py`: one module-level pure function (`nudge`)
beside `pixel_to_mood`, and — inside the existing `create()` → `index()`
closure (FE-4/FE-5) — one extra closure plus two configuration calls on the
existing `pad` handle. `frontend/__init__.py`, `app.py`, `frontend/api.py`
and the imports of `mood_pad.py` are all unchanged (`events` is already
imported and is where `GenericEventArguments` lives).

#### The pure function, literally

```python
STEP = 0.05

_NUDGES: dict[str, tuple[float, float]] = {
    "ArrowRight": (STEP, 0.0),
    "ArrowLeft": (-STEP, 0.0),
    "ArrowUp": (0.0, STEP),
    "ArrowDown": (0.0, -STEP),
}


def nudge(valence: float, energy: float, key: str) -> tuple[float, float]:
    """Move a ``(valence, energy)`` pair one step in ``key``'s direction."""
    if key not in _NUDGES:
        return valence, energy
    d_valence, d_energy = _NUDGES[key]
    return (
        round(min(1.0, max(-1.0, valence + d_valence)), 2),
        round(min(1.0, max(-1.0, energy + d_energy)), 2),
    )
```

Load-bearing, each pinned by a test in `tests/test_mood_pad.py`:

- **Return order is `(valence, energy)`**, same as `pixel_to_mood` and same as
  `nudge`'s own parameters, so the handler can do `set_mood(*nudge(...))`
  exactly like FE-5 does `set_mood(*pixel_to_mood(...))`. FE-4's entry explains
  why this order is the opposite of the rest of the codebase and why that must
  not be "fixed".
- **Clamp before round, not after.** `0.98 + 0.05` is `1.0300000000000002`;
  clamping first yields exactly `1.0`, and `round(1.0, 2)` leaves it. Rounding
  first would give `1.03` and the clamp would still save it here, but the order
  above keeps the edge value bit-identical to the literal `1.0` the four
  clamp tests compare with `==`.
- **`round(..., 2)` is behavioural, not cosmetic.** Three `ArrowUp`s from the
  origin must land on exactly `0.15`, not `0.15000000000000002` — the tests
  assert exact float equality, deliberately not `pytest.approx`, because the
  value is POSTed verbatim by FE-5's `log_mood()`. Do not drop the rounding
  "because the readout formats to 2 decimals anyway"; the readout is not the
  only consumer.
- **A non-arrow key returns the inputs untouched**, via the early return —
  not `round()`ed inputs. `("Enter", "Escape", "a", "Tab", "")` are all
  parametrized no-op cases, and `""` in particular means the handler may pass
  a missing key through without a separate guard.
- **`STEP` is module-level and named**; `tests/test_mood_pad.py` defines its
  own `STEP = 0.05` constant and compares against it, so the value is pinned
  at 0.05 but the two constants are independent — the test does not import it.

Knowingly accepted duplication: the `min(1.0, max(-1.0, ...))` clamp now
appears in both `pixel_to_mood` and `nudge`. Extracting a `_clamp()` helper
would mean editing FE-4's already-green function for no behavioural reason, so
FE-6a leaves it. If a third clamp site appears, extract then.

Consequence worth knowing (not test-observable, not a bug): `pixel_to_mood`
does *not* round, so a drag leaves `current_valence`/`current_energy`
un-rounded; the first nudge afterwards snaps them onto the 2-decimal grid. The
readout already displays 2 decimals, so the jump is invisible there — it shows
up only in the value POSTed to `/moods`, and rounding it is the requirement.

#### The wiring, literally

Inside `index()`, `handle_key` is defined immediately after FE-4's
`handle_mouse`, and the two configuration calls go immediately after the
`pad = ui.interactive_image(...)` statement (before `readout = ui.label(...)`,
which `set_mood` only touches at call time, so ordering is safe):

```python
        def handle_key(event: events.GenericEventArguments) -> None:
            key = event.args.get("key", "")
            # FE-6b hooks in here: `if key == "Enter": await log_mood()` —
            # which makes this handler async, so keep that in mind rather
            # than adding a second keydown subscription.
            valence, energy = nudge(current_valence, current_energy, key)
            if (valence, energy) != (current_valence, current_energy):
                set_mood(valence, energy)

        pad = ui.interactive_image(...)   # FE-4, unchanged
        pad.props("tabindex=0")
        pad.on("keydown", handle_key, args=["key"])
```

`handle_key` reads `current_valence`/`current_energy` but never rebinds them
(`set_mood` owns that), so it needs **no `nonlocal`** — unlike `handle_mouse`,
which does rebind `dragging`. Adding one would be harmless but misleading.

The `(valence, energy) != (current_valence, current_energy)` guard is FE-6a's
one call beyond the row's text: `nudge` already makes a non-arrow key a no-op
arithmetically, but calling `set_mood` unconditionally would still reassign
`pad.content` and `readout.text` and enqueue a full SVG update over the
websocket on *every* keystroke while the pad has focus — including held arrow
keys repeating against a clamped edge. Not observable in any test either way;
the guard is 2 lines and skips the traffic. `set_mood` remains the single
writer of state + marker + readout, per FE-5's Decision 1 — the handler must
not touch `pad.content`, `readout.text`, or the two floats directly.

#### `.on('keydown', handler, args=['key'])` — what actually reaches the handler

Verified by reading NiceGUI 3.16.0 in `.pixi/envs/default`, not recalled, and
verified for `.on()` specifically rather than inherited from `ui.keyboard`
(which has its own `KeyEventArguments` wrapper and is *not* what this uses):

1. `Element.on()` (`nicegui/element.py:397`) normalizes a flat
   `args=['key']` to `[['key']]` — "for the first emitted argument, keep only
   the `key` field". So `args=['key']` and `args=[['key']]` are the same call.
2. Client-side, the default `js_handler` `(...args) => emit(...args)` passes
   the raw DOM `KeyboardEvent` as the single argument;
   `stringifyEventArgs` (`nicegui/static/nicegui.js:176-201`) filters it to the
   requested keys and JSON-**stringifies** it, so the socket message carries
   `args: ['{"key":"ArrowUp"}']`.
3. Server-side, `Client.handle_event` (`nicegui/client.py:401-403`)
   `json.loads` each element **and unwraps the list when there is exactly
   one**: `if len(msg['args']) == 1: msg['args'] = msg['args'][0]`.

So the handler receives an `events.GenericEventArguments` whose `.args` is the
**dict `{"key": "ArrowUp"}`** — not a list, not a JSON string, not a
`KeyboardEvent`-like object with attribute access. `event.args["key"]` /
`event.args.get("key", "")` is the correct read; `event.key`,
`event.args[0]["key"]` and `json.loads(event.args)` all fail. Keeping
`args=['key']` (rather than `None`, which sends the whole event) is what keeps
the message small and is why only `key` is available — `shiftKey`, `repeat`,
etc. are not delivered and must not be assumed.

Two more facts that make this land on the right DOM node, both from
`nicegui/elements/interactive_image.js`: the component's template has a
**single root `<div>`**, and its declared `props` are only
`src, content, size, events, cross, t, sanitize`. `tabindex` and the
`onKeydown` listener are therefore both `$attrs` fallthrough and Vue 3 applies
both to that same root div — so the element that becomes focusable is exactly
the element that receives the key events. This is also why the pad's existing
`on_mouse`/`events=` channel cannot serve: those are wired to the inner
`<img>`'s `v-on` and emit a fixed `mouse` payload (`mouse_event_type`,
`image_x`, `image_y`, `button`, `buttons`, and the four modifier flags) with
no key identity anywhere in it.

`pad.props("tabindex=0")` renders as the **string** `"0"`, not the int `0`:
`Props.parse` (`nicegui/props.py:172`) `ast.literal_eval`s only quoted/bracketed
values and stores an unquoted one verbatim. That is exactly what
`test_mood_pad_is_keyboard_focusable` asserts, so `props("tabindex=0")` is
required and `props('tabindex="0"')` would render `0` and fail. Both calls
return `Self`, so chaining them into one statement is equivalent; two
statements are pinned only for readability.

#### Open UX detail, deliberately not designed around

With the pad focused, `ArrowUp`/`ArrowDown` also **scroll the page**, because
the default `js_handler` does not `preventDefault()`. Suppressing it would mean
changing the mechanism the requirement settled (`js_handler=`, or a
`.on('keydown.prevent', ...)` modifier — which NiceGUI does support, see
`event_listener.py:30-35`, but which would apply to *every* key, swallowing
`Tab` and trapping keyboard focus on the pad). FE-6a therefore ships without
it. Confirm the actual severity in the manual check below; if it is
disruptive, it is a new decision (a per-arrow-key subscription, or a scoped
`js_handler`), not a silent amendment here.

Out of scope, deliberately: Enter-to-submit (FE-6b — the seam is the comment
in `handle_key` above); any visible focus ring or `autofocus`; any other key
binding; any auth guard on `/`; any change to `nudge`'s step size per modifier
key (the `key`-only payload could not support it anyway).

**Traceability:** FE-6a → `frontend.mood_pad.nudge()` plus the `handle_key()`
closure and the `pad.props("tabindex=0")` / `pad.on("keydown", handle_key,
args=["key"])` calls inside `frontend.mood_pad.create()`'s `index()` page in
`backend/app/frontend/mood_pad.py`. Split in two, the same shape as FE-4/FE-5.
**Automated slice:** the 11 `nudge` unit tests at the end of
`backend/app/tests/test_mood_pad.py`, plus
`backend/app/tests/test_frontend.py::test_mood_pad_is_keyboard_focusable`
(plain `client` fixture; `tabindex` is a server-rendered prop). **Manual
slice** (dev server from `backend/app/`, per the Testing policy; all four
required, result recorded in the commit message):

1. *Focus* — `Tab` to the pad (or click it) and confirm it takes focus, then
   press each arrow key once and confirm the marker steps and the readout
   changes by 0.05 in the expected direction (Up = higher energy, Right = more
   pleasant).
2. *Lockstep with a drag* — drag to an off-centre point, then nudge: the
   marker must continue from where the drag left it, not jump to the origin,
   and the readout must agree with the marker.
3. *Clamp* — hold an arrow key until the marker reaches an edge and confirm it
   stops there, with the readout pinned at `±1.00` rather than continuing.
4. *Page scroll* — note whether `ArrowUp`/`ArrowDown` scroll the page while
   the pad is focused (see the open UX detail above) and record the answer,
   whatever it is.

### FE-6b — Enter on the focused pad submits the mood

No new component, no new file, no new function, no new element, no new
event subscription, and no contract change to anything. FE-6b is a second
*trigger* for FE-5's already-contracted `log_mood()`, wired into FE-6a's
already-contracted `handle_key` at the seam FE-6a left for it. The whole
change is four lines inside
`backend/app/frontend/mood_pad.py`'s `create()` → `index()` closure.

#### The change, literally

`handle_key` becomes `async def` and gains an Enter branch in place of the
FE-6b placeholder comment; nothing else in the file moves:

```python
        async def handle_key(event: events.GenericEventArguments) -> None:
            key = event.args.get("key", "")
            if key == "Enter":
                await log_mood()
                return
            valence, energy = nudge(current_valence, current_energy, key)
            if (valence, energy) != (current_valence, current_energy):
                set_mood(valence, energy)
```

The `pad.on("keydown", handle_key, args=["key"])` call is **unchanged** —
same single subscription, same `args=["key"]` payload. Adding a second
`.on("keydown", ...)` for Enter is explicitly wrong: it would give the pad
two listeners racing on the same DOM event and two places to keep in sync.

Load-bearing details:

- **Calling `log_mood()` — the function — is the contract, not
  re-implementing its body.** "Identical POST, identical 201/401/else
  branches, identical logged-out short-circuit" is satisfied by there being
  exactly one implementation. Any copy of the request, the header, or the
  short-circuit into `handle_key` is drift and must be rejected in review,
  even if it looks identical at the time.
- **Early return on Enter, before `nudge`.** Behaviourally this is a free
  choice: `"Enter"` is not in `_NUDGES`, so FE-6a's guard already makes it a
  no-op on the marker (and `("Enter", ...)` is a pinned parametrized no-op
  case in `tests/test_mood_pad.py`). Late ordering would work identically.
  Early return is chosen so the one `await` sits alone in its own branch and
  the nudge path keeps its FE-6a shape verbatim.
- **`await` on `log_mood()` and nothing else.** The nudge branch stays
  fully synchronous; `set_mood` and `nudge` are not coroutines and must not
  become ones.
- **`handle_key` still needs no `nonlocal`.** It reads
  `current_valence`/`current_energy` (via `log_mood`, which reads them
  itself) and never rebinds them; `set_mood` remains the single writer of
  state + marker + readout, per FE-5's Decision 1.
- **Do not reorder the closures to "fix" the forward reference.**
  `handle_key` (defined at the top of `index()`) names `log_mood` (defined
  near the bottom) through the enclosing scope's cell, resolved at *call*
  time — and `index()` has fully executed before any keydown can arrive, so
  the name is always bound. Moving `handle_key` below `log_mood` would in
  turn break its references to `pad`/`readout` ordering assumptions for no
  gain.

#### Async safety: confirmed, not assumed

`Element.on()` handlers reach `events.handle_event()` via
`Element._handle_event` (`nicegui/element.py:409-413`) — the same function
`ui.button(on_click=...)` uses. `handle_event`
(`nicegui/events.py:455-488`) calls the handler inside the sender's
`parent_slot`, and when the result is awaitable schedules
`_await_and_handle_in_context(result, parent_slot)` via
`background_tasks.create_or_defer`, which **re-enters that same slot context
before awaiting** and routes exceptions to `app.handle_exception`. So an
`async` `handle_key` gets exactly the treatment FE-5's `async log_mood`
already gets from the button: `ui.notify` and `ui.navigate.to` inside it
resolve against the right client, and a raised exception does not escape
into the websocket loop. Read from NiceGUI 3.16.0 in `.pixi/envs/default`,
not recalled.

#### Open UX detail, deliberately not designed around

**Holding Enter submits repeatedly.** A held key fires repeating `keydown`
events, each dispatching `log_mood()`, each POSTing a duplicate mood.
FE-6a's `args=["key"]` payload delivers only `key`, so the DOM event's
`repeat` flag never reaches the server and the handler structurally cannot
distinguish a repeat from a fresh press. Suppressing it would mean changing
the payload (`args=["key", "repeat"]`) or the mechanism, i.e. reopening a
decision FE-6a settled and FE-6b's row explicitly scopes out ("no new
behavior, no new test target"). FE-6b therefore ships without it, the same
way FE-6a shipped without `preventDefault()` on the arrow keys. Manual step
6 below records the actual severity; if it is disruptive, the fix is a new
requirement (debounce, an in-flight guard that also covers the button, or a
`repeat`-aware payload), **not** a silent amendment here. Note also that no
`preventDefault()` question arises for Enter itself: the pad is a plain
focusable `<div>`, not a form control, and `/` renders no `<form>`, so Enter
has no default browser action to suppress.

Out of scope, deliberately: any other key binding; a visible focus ring or
`autofocus`; disabling the button or the key while a request is in flight;
any auth guard on `/`; any change to `log_mood`, `set_mood`, `nudge`,
`frontend/api.py`, `frontend/__init__.py` or `app.py`.

**Traceability:** FE-6b → the `if key == "Enter": await log_mood()` branch
in the `handle_key()` closure of `frontend.mood_pad.create()`'s `index()`
page, `backend/app/frontend/mood_pad.py`. **No automated tests, and none
are expected** — unlike FE-4/FE-5/FE-6a this item has no server-observable
slice at all: it adds no element, no prop, and no pure function, so there is
nothing for the `client` fixture or a unit test to see, and the action
underneath is already covered by FE-5's tests plus `tests/test_moods.py`.
Adding a test that asserts `handle_key` is a coroutine function would test
the implementation, not the behavior; do not. Per the FE-1 Testing policy
the NiceGUI `user`/`Screen` fixtures remain banned, so verification is
**manual only** (dev server from `backend/app/`; all six required, result
recorded in the commit message):

1. *Logged-out short-circuit* — in a fresh private window with no
   `app.storage.user` entries, click the pad once to focus it, press Enter,
   and confirm the notification "Please log in to record a mood." and
   navigation to `/login` — identical to FE-5's manual step 4.
2. *Success from a dragged value* — logged in, drag the marker to a
   distinctive off-centre point, press Enter (the pad still holds focus
   after the drag) and confirm "Mood logged!" plus the marker and readout
   snapping back to centre / `0.00`.
3. *Success from a nudged value, posted verbatim* — logged in, from the
   centre press `ArrowUp` three times and `ArrowRight` once so the readout
   reads `Energy: 0.15 · Valence: 0.05`; press Enter, then
   `GET /users/{username}/moods` (curl with the same bearer token, or
   `/docs`) and confirm the newest mood is exactly `energy: 0.15`,
   `valence: 0.05` — not swapped, and not `0.15000000000000002`. This is the
   step that proves FE-6a's rounding survives to the wire and that the pair
   is not flipped.
4. *401 branch* — set `token` in `backend/app/.nicegui/storage-user-*.json`
   to a garbage string, reload `/`, focus the pad, press Enter, and confirm
   the same notification and redirect as step 1 (this exercises the real
   response branch where step 1 exercises the short-circuit).
5. *Pad not focused does nothing* — click blank page area so the pad loses
   focus, press Enter, and confirm no notification, no navigation, and no
   new mood in `GET /moods`. Be careful that focus is not on the "Log this
   mood" button: Enter on a focused `<button>` is native browser click
   activation and would legitimately submit, which is unchanged behavior and
   not what this step is checking.
6. *Key repeat* — logged in, hold Enter for ~2 seconds, then count the
   notifications and the moods added by `GET /users/{username}/moods`.
   Record the count whatever it is; see the open UX detail above.

### FE-7 — The mood history page at `/history`

No new component. New file **`backend/app/frontend/history.py`** — the third
per-module page file, after FE-3a's `frontend/auth.py` and FE-4's
`frontend/mood_pad.py`, with the same `create() -> None` shape.
`frontend/__init__.py` gains `from . import history` and one call in
`create_pages()`; `frontend/mood_pad.py` gains exactly one line; `app.py`,
`frontend/api.py` and `pyproject.toml` are untouched.

```python
def create_pages() -> None:
    """Register every NiceGUI page."""
    mood_pad.create()
    auth_pages.create()
    history.create()
```

#### The pure function (the one unit-tested thing)

```python
def quadrant_label(energy: float, valence: float) -> str:
    """Name the circumplex quadrant an ``(energy, valence)`` pair falls in."""
    if abs(energy) < 0.1 and abs(valence) < 0.1:
        return "Neutral"
    elif energy > 0 and valence > 0:
        return "High Energy Pleasant"
    elif energy > 0 and valence < 0:
        return "High Energy Unpleasant"
    elif energy < 0 and valence > 0:
        return "Low Energy Pleasant"
    else:
        return "Low Energy Unpleasant"
```

This is `analytics.get_mood_quadrant_name` **branch for branch**, differing
only in the returned strings (Title Case with spaces instead of snake_case).
Read from `backend/app/analytics.py:214-234`, not recalled. Load-bearing,
each point pinned by a test in `tests/test_history.py`:

- **Parameter order is `(energy, valence)`** — energy first, matching
  `analytics`, `MoodModel`, `schemas` and `_readout`, and matching the tests'
  positional calls. Note this is the *opposite* of `mood_pad.pixel_to_mood` /
  `nudge`, which are valence-first (FE-4 explains why that asymmetry exists);
  `history.py` never touches those, so nothing here has to reconcile them —
  but do not "harmonize" this signature to match them.
- **`<`, not `<=`, on the neutral band.** `(0.09, 0.09)` is Neutral;
  `(0.1, 0.1)` is High Energy Pleasant and `(-0.1, -0.1)` is Low Energy
  Unpleasant. `abs(0.1) < 0.1` is `False` because both sides are the same
  float, so no epsilon fudge is needed or wanted.
- **Both axes must be inside the band for Neutral** — `(0.1, 0.0)` is not
  Neutral, because the `and` fails on energy.
- **The final `else` is a catch-all, not a genuine low/unpleasant test.**
  `(0.5, 0.0)` — high energy, exactly zero valence — misses all three strict
  inequalities and returns "Low Energy Unpleasant". That is a quirk of the
  source; `test_a_point_on_the_valence_axis_falls_through_to_low_energy_unpleasant`
  pins it deliberately. Replicating "exactly" means replicating this too. Do
  not add a `valence == 0` branch to make it "correct" — that is a change to
  `analytics.get_mood_quadrant_name`'s behavior and would need its own
  requirement, applied to both copies.

**Knowingly accepted duplication, and the one maintenance rule it carries.**
This is the sanctioned local-re-derivation exception in the Boundaries
section — `frontend/` must not import `analytics`, and round-tripping to the
API for a label it can compute from data it already holds would be worse.
The cost is a second copy of the classification: **if the thresholds or
branch order in `analytics.get_mood_quadrant_name` ever change, this function
changes in the same commit.** Flagging it here rather than letting a future
reader discover two disagreeing classifiers.

#### The page, literally

Module constants, so the three fixed strings have one definition each:

```python
EMPTY_PROMPT = "No mood entries yet. Click on the mood board to record your first mood!"
LOGIN_PROMPT = "Please log in to view your mood history."
GENERIC_FAILURE = "Could not complete the request."
HISTORY_LIMIT = 10

_COLUMNS = [
    {"name": "timestamp", "label": "Timestamp", "field": "timestamp", "align": "left"},
    {"name": "energy", "label": "Energy", "field": "energy", "align": "left"},
    {"name": "valence", "label": "Valence", "field": "valence", "align": "left"},
    {"name": "quadrant", "label": "Quadrant", "field": "quadrant", "align": "left"},
    {"name": "notes", "label": "Notes", "field": "notes", "align": "left"},
]
```

Two pure row helpers, kept out of the page body because they build data, not
elements:

```python
def _format_timestamp(raw: str) -> str:
    """Render a MoodResponse's naive-UTC ISO timestamp as ``%Y-%m-%d %H:%M UTC``."""
    return datetime.fromisoformat(raw).strftime("%Y-%m-%d %H:%M UTC")


def _history_row(mood: dict) -> dict:
    """Turn one MoodResponse JSON object into one ui.table row."""
    energy = mood["energy"]
    valence = mood["valence"]
    return {
        "id": mood["id"],
        "timestamp": _format_timestamp(mood["timestamp"]),
        "energy": f"{energy:.2f}",
        "valence": f"{valence:.2f}",
        "quadrant": quadrant_label(energy, valence),
        "notes": mood.get("notes") or "",
    }
```

and the page itself (`from datetime import datetime`, `from nicegui import
app, ui`, `from . import api`):

```python
def create() -> None:
    """Register the /history page."""

    @ui.page("/history", title="Mood history")
    async def history() -> None:
        username = app.storage.user.get("username")
        token = app.storage.user.get("token")
        if not username or not token:
            ui.label(EMPTY_PROMPT)
            return

        async with api.client() as http:
            response = await http.get(
                f"/users/{username}/moods",
                params={"limit": HISTORY_LIMIT},
                headers={"Authorization": f"Bearer {token}"},
            )

        if response.status_code == 200:
            moods = response.json()
            if moods:
                ui.table(columns=_COLUMNS, rows=[_history_row(m) for m in moods], row_key="id")
            else:
                ui.label(EMPTY_PROMPT)
        elif response.status_code == 401:
            ui.label(LOGIN_PROMPT)
            ui.navigate.to("/login")
        else:
            ui.label(GENERIC_FAILURE)
```

Load-bearing details:

- **`async def` page function, and it is genuinely supported** — but not the
  way the sync pages are. `page._wrap`'s `decorated`
  (`nicegui/page.py:163-219`, 3.16.0, read not recalled) calls the page
  function, sees an awaitable, and runs it in a **background task** wrapped in
  `with client:`, racing it against the client's connection wait with
  `timeout=self.response_timeout` (**3.0 s** by default). Two consequences
  that matter here. (1) The elements built inside the coroutine *are* in the
  server-delivered HTML, because the task finishes long before the timeout and
  `client.build_response` runs after `asyncio.wait` returns — which is what
  makes `test_history_page_shows_the_empty_prompt_when_logged_out` a
  meaningful assertion. (2) If the fetch ever became slow, NiceGUI would serve
  a 500 "took longer than response_timeout" page instead. The in-process
  ASGI call is sub-millisecond and `GET /users/{username}/moods` is a **sync**
  `def` endpoint (FastAPI runs it in the threadpool, so it cannot block the
  loop), so 3 s is ample. If a later item needs a slow page fetch, the escape
  hatch is `await ui.context.client.connected()` before the slow work, **not**
  raising `response_timeout`.
- **Read `app.storage.user` before the first `await`.** `app.storage.user`
  resolves through `storage.request_contextvar`, set by NiceGUI's
  `RequestTrackingMiddleware` (`nicegui/storage.py:31-50`). That middleware is
  installed on `core.app` — the *mounted sub-app* — not on the parent FastAPI
  instance (`ui_run_with.py:106` → `set_storage_secret(..., parent_app=app)`,
  which appends it to `core.app.user_middleware`), and `/users/...` matches a
  parent route registered before the mount, so the in-process call does not
  re-enter it and cannot clobber the contextvar. Reading first is nonetheless
  the rule: `httpx.ASGITransport` awaits the app *inline in this task*, so any
  future middleware change that did set the contextvar would silently
  repoint `app.storage.user` mid-page. FE-5's `log_mood()` already reads first
  for the same reason.
- **Logged-out short-circuit renders the empty prompt and returns**, before
  any request is built — same reasoning as FE-5's: `f"/users/{None}/moods"` is
  a wrong URL and `f"/users//moods"` matches no route. The requirement
  independently mandates that a logged-out visitor and a zero-mood logged-in
  user see the *same* string, so `EMPTY_PROMPT` has exactly one definition and
  two call sites.
- **No auth guard, and `ui.navigate.to` is not one here either.** `/history`
  returns 200 to a logged-out visitor and renders the prompt; the 401 branch
  renders `LOGIN_PROMPT` and *then* navigates. Enqueued during page build with
  no socket yet, the `open` message sits in `Outbox.messages` until
  `has_socket_connection` becomes true (`nicegui/outbox.py:95-125`) and fires
  right after load — so the message is briefly visible before the redirect,
  which is exactly the intent. Nothing is being withheld, so FE-3b's
  `RedirectResponse` forward pointer is still **not** triggered and stays open.
- **Inline `ui.label`s, not `ui.notify`, for both failure branches** — the
  row's instruction, and correct as written: a page *load* has no click to
  attach a toast to, a toast auto-dismisses (so a user landing on a blank page
  would have no idea why), and on the 401 branch the navigation would race the
  toast off-screen. Not a deviation; recording the reasoning because FE-3b and
  FE-5 use `ui.notify` for the same status codes and the difference is
  deliberate.
- **Status code first, body never** (FE-3b's rule, third application): 200 →
  401 → `else`. The `else` absorbs 403, 404, 422, every 5xx and the
  synthesized 500 from `api.client()`'s `raise_app_exceptions=False`. The raw
  response body must never reach the page.
- **Newest-first is the API's order, preserved by not touching it.**
  `get_moods` (`app.py:329-331`) already does
  `.order_by(MoodModel.timestamp.desc()).offset(skip).limit(limit)`, so rows
  are built in iteration order and never re-sorted. Correspondingly the
  columns are declared **explicitly and without `sortable`**: passing
  `columns=None` would make NiceGUI auto-generate `{'sortable': True}` for
  every key (`nicegui/elements/table.py:65-67`), handing the user a way to
  break the pinned ordering, and would label the columns `TIMESTAMP` /
  `ENERGY` in caps. `align: "left"` is cosmetic (Quasar right-aligns
  non-first columns by default, which reads badly for these formatted
  strings). `pagination` is left unset — 10 rows, so `hide-pagination` is
  right.
- **`row_key="id"` needs `"id"` in every row**, hence the mood's own `id`
  being carried into the row dict even though no column displays it. It is
  the natural stable key and it is already unique per mood.
- **Formatting is done server-side into strings**, not left as floats with a
  Quasar `:format`: `{value:.2f}` matches `mood_pad._readout`'s style, and
  `%Y-%m-%d %H:%M UTC` is correct because `MoodModel.timestamp` is a naive
  UTC `DateTime` and there is no reliable client timezone. Consequence worth
  knowing: `datetime.fromisoformat` would happily parse an offset-bearing
  string and `strftime` would then print that offset's wall time labelled
  "UTC" — not reachable today (the column is naive), but it is why this must
  not be "improved" into a general timestamp formatter without revisiting.
- **`params={"limit": HISTORY_LIMIT}`**, not a hand-built query string —
  httpx encodes it. The `username` in the path stays un-encoded, matching
  FE-5's `f"/users/{username}/moods"`; that is pre-existing and out of scope
  here, not an endorsement.

#### `api.client()` is unchanged — and this is the *second* authenticated
call site, not the third

FE-5's forward pointer says to revisit the `Authorization`-header shape "when
a third authenticated call site lands (FE-7/FE-8/FE-9)". FE-7 is the second
(FE-5's `log_mood()` is the first), so the trigger is **not** met: headers
stay per-request, `api.client()` keeps its no-argument signature, and no
`api.auth_headers()` / `api.client(token=...)` helper is introduced. Extract
at FE-8 or FE-9, with three real usages to design against. Per FE-3b, the
stored token carries no `token_type` prefix, so this handler writes
`f"Bearer {token}"` itself.

#### The one-line change to `frontend/mood_pad.py`

```python
        ui.button("Log this mood", color="high-energy-pleasant", on_click=log_mood)
        ui.link("History", "/history")
```

Appended as the **last statement of `index()`**, after the button. Any
position satisfies `test_root_page_links_to_history` (`_has_props` scans all
elements), so this is a placement call: appending leaves FE-4/FE-5/FE-6's
pad → readout → button construction order byte-identical, which keeps their
render-order-sensitive assertions untouched, and it reads as a footer nav
below the primary action. It must be `ui.link` — `ui.button(on_click=lambda:
ui.navigate.to(...))` renders no `href` prop and fails the test (FE-3a's
finding, third time it applies). Nothing else in `mood_pad.py` changes.

Out of scope, deliberately: journal entries (FE-8's own page); any back-link
from `/history` to `/` (not in the requirement — do not invent one);
pagination, filtering, sorting or a configurable limit; editing or deleting a
mood from the table; any auth guard on any page; a "logged in as…" indicator;
any change to `frontend/api.py`, `app.py`, `analytics.py` or the REST layer.

**Traceability:** FE-7 → `frontend.history.quadrant_label()` plus
`frontend.history.create()`'s `/history` page in
`backend/app/frontend/history.py`, registered from `frontend.create_pages()`
in `backend/app/frontend/__init__.py`, plus the single
`ui.link("History", "/history")` in `frontend.mood_pad.create()`'s `index()`.
Split in two, the same shape as FE-4/FE-5/FE-6a.

**Automated slice** — 13 tests, all with the plain `client` fixture or no
fixture at all, per the FE-1 Testing policy:

- `backend/app/tests/test_history.py` — 10 unit tests on `quadrant_label`
  alone: one per quadrant well outside the band (4), the origin, just-inside
  `(0.09, 0.09)`, the `±0.1` boundary in both directions, one-axis-only at the
  boundary, and the catch-all `else` at `(0.5, 0.0)`. No fixture, no HTTP.
- `backend/app/tests/test_frontend.py` — `test_history_page_is_served_without_an_auth_guard`
  (`GET /history` with `follow_redirects=False` → 200, i.e. no guard),
  `test_history_page_shows_the_empty_prompt_when_logged_out` (the exact
  `EMPTY_PROMPT` string is in the server-rendered HTML — this is the one test
  that proves the async page body's elements survive into the response), and
  `test_root_page_links_to_history` (an element on `/` carries
  `href="/history"`).

Nothing else in FE-7 is TestClient-reachable: `app.storage.user` cannot be
seeded over HTTP, so no automated test can reach the authenticated branch,
and `GET /users/{username}/moods` itself is already covered by
`tests/test_moods.py` — do not re-test it through the UI. (Caveat for anyone
adding tests later: `test_frontend.py`'s `_rendered_props` brace-depth parser
would mis-parse a populated table only if a mood's `notes` contained a literal
`{` or `}`; that path is unreachable from the `client` fixture, so it is a
note, not a constraint on this design.)

**Manual slice** (dev server from `backend/app/`, per the Testing policy; all
five required, result recorded in the commit message):

1. *Populated table* — logged in with at least three moods logged from `/`,
   open `/history` and confirm a table with the five columns Timestamp /
   Energy / Valence / Quadrant / Notes; the newest mood is the **top** row;
   timestamps read `2026-08-27 14:05 UTC`; Energy and Valence show two
   decimals; the Quadrant of an obviously top-right mood reads "High Energy
   Pleasant" and a centred one reads "Neutral"; a mood with no note shows a
   blank Notes cell rather than "None". Check the Energy/Valence pair is not
   swapped against what the pad's readout showed when it was logged.
2. *Limit* — with more than ten moods logged, confirm exactly ten rows.
3. *Zero moods but logged in* — register a fresh user, log in, go straight to
   `/history` and confirm the same string as the logged-out case, "No mood
   entries yet. Click on the mood board to record your first mood!", and **no**
   table.
4. *401 branch* — edit `token` in `backend/app/.nicegui/storage-user-*.json`
   to a garbage string, load `/history`, and confirm the page shows "Please
   log in to view your mood history." and then navigates to `/login` (the
   message is briefly visible first — that is expected, see the bullet above).
5. *Generic failure branch* — set `username` in that same storage file to
   another existing user, making the API answer 403, and confirm the page
   shows exactly "Could not complete the request." with no response body, no
   traceback and no navigation.

Also worth eyeballing during step 1: the `ui.link("History", "/history")` on
`/` and that following it does not disturb the pad (a full page load, so the
marker resets to centre — expected).

### FE-8a — The read-only journal listing at `/journal`

No new component. New file **`backend/app/frontend/journal.py`** — the fourth
per-module page file, after `frontend/auth.py` (FE-3a), `frontend/mood_pad.py`
(FE-4) and `frontend/history.py` (FE-7), with the same `create() -> None`
shape. `frontend/__init__.py` gains `journal` in its import line and one call
in `create_pages()`; `frontend/mood_pad.py` gains exactly one line; `app.py`,
`frontend/api.py`, `frontend/history.py` and `pyproject.toml` are untouched.

```python
from . import auth as auth_pages
from . import history, journal, mood_pad


def create_pages() -> None:
    """Register every NiceGUI page."""
    mood_pad.create()
    auth_pages.create()
    history.create()
    journal.create()
```

The page is **structurally FE-7's `/history` with a different fetch and a
different renderer**. That is the point: it is the second instance of a shape
FE-7 already justified in detail, so the bullets below cover only what differs
or is newly decided, and defer the rest to FE-7's entry rather than restating
it. Anything FE-7 settled (async page body inside NiceGUI's 3 s
`response_timeout`, reading `app.storage.user` before the first `await`,
logged-out short-circuit before any URL is built, inline `ui.label` rather
than `ui.notify` for page-load failures, status-code-first/body-never,
`params=` not a hand-built query string) applies here unchanged.

#### The module, literally

```python
"""The journal entries page, at /journal."""

from datetime import datetime

from nicegui import app, ui

from . import api

JOURNAL_EMPTY = "No journal entries yet."
LOGIN_PROMPT = "Please log in to view your journal."
GENERIC_FAILURE = "Could not complete the request."
JOURNAL_LIMIT = 10


def _format_timestamp(raw: str) -> str:
    """Render an EntryResponse's naive-UTC ISO timestamp as ``%Y-%m-%d %H:%M UTC``."""
    return datetime.fromisoformat(raw).strftime("%Y-%m-%d %H:%M UTC")


def create() -> None:
    """Register the /journal page."""

    @ui.page("/journal", title="Journal")
    async def journal() -> None:
        username = app.storage.user.get("username")
        token = app.storage.user.get("token")
        if not username or not token:
            ui.label(JOURNAL_EMPTY)
            return

        async with api.client() as http:
            response = await http.get(
                f"/users/{username}/entries",
                params={"limit": JOURNAL_LIMIT},
                headers={"Authorization": f"Bearer {token}"},
            )

        if response.status_code == 200:
            entries = response.json()
            if entries:
                with ui.column():
                    for entry in entries:
                        with ui.card():
                            ui.label(_format_timestamp(entry["timestamp"]))
                            ui.label(entry["content"])
            else:
                ui.label(JOURNAL_EMPTY)
        elif response.status_code == 401:
            ui.label(LOGIN_PROMPT)
            ui.navigate.to("/login")
        else:
            ui.label(GENERIC_FAILURE)
```

Load-bearing details:

- **`ui.column` of `ui.card`, not `ui.table` — and the container exists only
  in the populated branch.** `EntryModel.content` / `schemas.EntryBase` allow
  1–5000 characters (read from `schemas.py:69-91`, not recalled), which a
  Quasar table cell clips to one line. Cards let the prose flow. Building the
  `ui.column` inside `if entries:` rather than around the whole branch keeps
  the logged-out and zero-entry DOM to a single `ui.label`, which is what the
  two `client`-fixture tests read.
- **`ui.label`, never `ui.html` / `ui.markdown`, for `content`.** Labels set
  text, so 5000 characters of arbitrary user prose cannot inject markup into
  the page. "Verbatim" in the requirement means *unmodified text*, not
  *rendered as authored*; do not "improve" this into `ui.markdown` — that
  would be a security change and a requirement change at once.
- **Exactly two labels per card, timestamp first.** The order is the contract
  (FE-8c appends an optional *third* label for the linked mood; if timestamp
  and content were swapped, that third one would land in the middle of the
  card).
- **The API's newest-first order is preserved by not touching it.**
  `get_entries` (`app.py:563-565`) already does
  `.order_by(EntryModel.timestamp.desc()).offset(skip).limit(limit)`, per
  REQ-ENTRY-3. No client-side `sorted()`, no `reverse=True` — same rule as
  FE-7's table rows.
- **`_format_timestamp` is a knowing second copy**, not an import. It is
  private in `frontend/history.py`, and importing an `_`-prefixed name across
  modules is worse than two identical two-liners. The row names the
  extraction trigger: a **third** consumer. See the flag below — FE-8c makes
  this decision worth re-reading, and the natural home if it is ever pulled
  out is a small shared `frontend/format.py`, not `history.py` (journal
  importing display helpers *from the history page module* would invert the
  dependency between two sibling pages).
- **`title="Journal"`** on the decorator, matching FE-7's
  `title="Mood history"`. Not pinned by any test; set it anyway, or NiceGUI
  titles the tab "NiceGUI" (FE-1's finding).
- **`mood_id` is fetched but not rendered, and no moods request happens
  here.** `EntryResponse` carries `mood_id`; FE-8a ignores it. Adding an
  N+1 `GET /users/{u}/moods/{id}` per card would be drift against FE-8c,
  which resolves the whole set with one windowed fetch.
- **`GET /users/{username}/entries` is a sync `def` endpoint** (`app.py:534`),
  so FastAPI runs it in the threadpool and it cannot block the event loop
  during the page's `await` — the same property that makes FE-7's 3 s
  `response_timeout` ample. Nothing here needs
  `await ui.context.client.connected()`.

#### This is the third authenticated call site — the trigger *is* met, and
FE-12 discharges it

FE-5's forward pointer (restated in FE-7's entry) says to extract an
`Authorization`-header helper "when a third authenticated call site lands".
`journal()` is that third site, after `mood_pad.log_mood()` and
`history.history()`. **FE-8a still writes `f"Bearer {token}"` inline, on
purpose**: bundling a three-file refactor into the commit that adds a page
would violate the one-logical-change-per-commit rule, and the refactor has
its own row — **FE-12**, which depends on FE-8a and extracts
`api.auth_headers(token)` across all three sites in one behaviour-free
commit. So the duplication here is scheduled, not overlooked. `api.client()`
keeps its no-argument signature in both items. If FE-12 is dropped or
deferred, this paragraph is the record that the trigger fired and was not
answered.

#### Open UX detail, deliberately not designed around

**Newlines inside an entry collapse.** `ui.label` renders into a `<div>` with
default `white-space: normal`, so a multi-line entry — which FE-8b's
`ui.textarea` makes the common case — displays as one run-on paragraph. The
fix is one cosmetic call (`.style("white-space: pre-wrap")`), but the row
specifies "exactly two `ui.label`s" and lists no styling, so FE-8a ships
without it and FE-8b's manual step 1 (save-success) is where the severity
becomes visible. If it reads badly, that is a new requirement, not a silent
amendment here. Same posture as FE-6b's key-repeat note.

Related note, not a constraint: `tests/test_frontend.py`'s `_rendered_props`
helper parses the served HTML by brace depth, so an entry whose `content`
contains a literal `{` or `}` could confuse it — exactly the caveat FE-7
recorded for mood `notes`. Unreachable from the `client` fixture (no
authenticated fetch), so it stays a note.

#### The one-line change to `frontend/mood_pad.py`

```python
        ui.link("History", "/history")
        ui.link("Journal", "/journal")
```

Appended as the **last statement of `index()`**, after FE-7's History link.
Same reasoning FE-7 gave: `_has_props` scans every element so any position
would pass, and appending leaves the pad → readout → button → History
construction order byte-identical. It must be `ui.link` — a
`ui.button(on_click=lambda: ui.navigate.to(...))` renders no `href` prop and
fails the test (FE-3a's finding, fourth application). Nothing else in
`mood_pad.py` changes, and `/` still has no auth guard.

#### Forward pointer for FE-8b

The `with ui.column(): ...` block, plus the `if entries:` / `else` around it,
is the body FE-8b lifts into its `@ui.refreshable` function — the fetch and
the failure branches are *not* part of that lift, or a save would silently
re-run the 401 branch. Keeping the container construction in one contiguous
block here is what makes that a move rather than a rewrite.

Out of scope, deliberately: the compose form and `POST /entries` (FE-8b);
rendering or selecting a linked mood (FE-8c); editing or deleting an entry;
pagination, "load more", filtering, search; any nav bar or back-link from
`/journal` to `/`; any auth guard on any page; any change to
`frontend/api.py`, `frontend/history.py`, `app.py` or the REST layer.

**Traceability:** FE-8a → `frontend.journal.create()`'s `/journal` page and
its private `_format_timestamp()` in `backend/app/frontend/journal.py`,
registered from `frontend.create_pages()` in
`backend/app/frontend/__init__.py`, plus the single
`ui.link("Journal", "/journal")` in `frontend.mood_pad.create()`'s `index()`.
Requirement: `TASKS.md`'s **FE-8a** row (epic "NiceGUI frontend redesign").
Split in two, the same shape as FE-4/FE-5/FE-6a/FE-7.

**Automated slice** — three tests, all with the plain `client` fixture, in
`backend/app/tests/test_frontend.py`:

- `test_journal_page_is_served_without_an_auth_guard` — `GET /journal` with
  `follow_redirects=False` → 200, i.e. no guard. The unfollowed response is
  what makes "no guard" testable at all.
- `test_journal_page_shows_the_empty_prompt_when_logged_out` — the exact
  `JOURNAL_EMPTY` string, `"No journal entries yet."`, is in the
  server-rendered HTML. Deliberately CTA-free so FE-8b's compose box does not
  force a wording change that would edit an already-passing test.
- `test_root_page_links_to_journal` — an element on `/` carries
  `href="/journal"`.

**No `tests/test_journal.py` in this item, and that is correct**: FE-8a
introduces no new pure function, and `_format_timestamp` is FE-7's two-liner
copied — unit-testing it a second time would pin
`datetime.fromisoformat(...).strftime(...)` twice without pinning anything
new. The first `test_journal.py` lands with FE-8c's `mood_line` /
`mood_option_label`. Everything else here sits behind an authenticated fetch
and `app.storage.user` cannot be seeded over HTTP; `GET /users/{u}/entries`
itself is already covered by `tests/test_entries.py` — do not re-test it
through the UI, and do not reach for the banned NiceGUI fixtures.

**Manual slice** (dev server from `backend/app/`, per the Testing policy; all
five required, result recorded in the commit message):

1. *Populated list* — logged in with at least three journal entries created
   via `POST /users/{username}/entries` (curl or `/docs`, since FE-8b's
   compose box does not exist yet), open `/journal` and confirm one card per
   entry, each showing a timestamp line then the content; the **newest entry
   is the top card**; timestamps read like `2026-08-27 14:05 UTC`; a long
   (~2000-character) entry is shown in full and not truncated.
2. *Limit* — with more than ten entries, confirm exactly ten cards.
3. *Zero entries but logged in* — register a fresh user, log in, go straight
   to `/journal` and confirm the string `"No journal entries yet."` and **no**
   cards — the same string the logged-out visitor sees.
4. *401 branch* — set `token` in `backend/app/.nicegui/storage-user-*.json`
   to a garbage string, load `/journal`, and confirm the page shows "Please
   log in to view your journal." and then navigates to `/login` (the message
   is briefly visible first — expected, per FE-7's outbox note).
5. *Generic failure branch* — set `username` in that same storage file to
   another existing user, making the API answer 403, and confirm the page
   shows exactly "Could not complete the request." with no response body, no
   traceback and no navigation.

Worth eyeballing during step 1: the `ui.link("Journal", "/journal")` on `/`
sits below the History link and both still work.

### FE-8b — The journal compose form at `/journal`

No new component and **no new file**: `backend/app/frontend/journal.py` is the
only file that changes. `frontend/__init__.py`, `frontend/api.py`,
`frontend/history.py`, `frontend/mood_pad.py`, `app.py`, the REST layer and
`pyproject.toml` are all untouched, and FE-8a's three passing tests keep
passing unchanged — `JOURNAL_EMPTY` stays verbatim and `/journal` stays
unguarded.

The handler is **FE-5's `log_mood()` shape applied to `POST /entries`**:
read-storage → short-circuit → `async with api.client()` →
201/401/`else`, status-code-first and body-never. Everything FE-5 settled
about that shape (why the logged-out case is short-circuited before the URL
is built, why `ui.notify` and not an inline label for *action* failures, why
the 401 branch's `ui.navigate.to("/login")` is post-action navigation rather
than an auth guard, why `f"Bearer {token}"` is written inline pending FE-12)
applies here unchanged and is not restated. What is new is the compose
element itself, the client-side length gate, and the `@ui.refreshable`
rewiring of FE-8a's list.

#### The module, literally (the whole updated `frontend/journal.py`)

```python
"""The journal entries page, at /journal.

See ARCHITECTURE.md's FE-8a entry for the read-only listing and FE-8b's
for the compose form: why entry_list is defined inside the page function
rather than at module scope, why validation runs before the request, and
why a successful save re-fetches the list instead of prepending the
POST's own response body.
"""

from datetime import datetime

import httpx
from nicegui import app, ui

from . import api

JOURNAL_EMPTY = "No journal entries yet."
LOGIN_PROMPT = "Please log in to view your journal."  # page-load 401
COMPOSE_LOGIN_PROMPT = "Please log in to write a journal entry."  # save 401
GENERIC_FAILURE = "Could not complete the request."
SAVE_SUCCESS = "Journal entry saved!"
CONTENT_INVALID = "Journal entry must be between 1 and 5000 characters."
COMPOSE_LABEL = "New journal entry"
SAVE_CAPTION = "Save entry"
CONTENT_MAX = 5000
JOURNAL_LIMIT = 10


def _format_timestamp(raw: str) -> str:
    """Render an EntryResponse's naive-UTC ISO timestamp as ``%Y-%m-%d %H:%M UTC``."""
    return datetime.fromisoformat(raw).strftime("%Y-%m-%d %H:%M UTC")


async def _fetch_entries(username: str, token: str) -> httpx.Response:
    """GET the newest ``JOURNAL_LIMIT`` journal entries for ``username``."""
    async with api.client() as http:
        return await http.get(
            f"/users/{username}/entries",
            params={"limit": JOURNAL_LIMIT},
            headers={"Authorization": f"Bearer {token}"},
        )


def create() -> None:
    """Register the /journal page."""

    @ui.page("/journal", title="Journal")
    async def journal() -> None:
        @ui.refreshable
        def entry_list(entries: list[dict]) -> None:
            if entries:
                with ui.column():
                    for entry in entries:
                        with ui.card():
                            ui.label(_format_timestamp(entry["timestamp"]))
                            ui.label(entry["content"])
            else:
                ui.label(JOURNAL_EMPTY)

        async def save_entry() -> None:
            content = (compose.value or "").strip()
            if not content or len(content) > CONTENT_MAX:
                ui.notify(CONTENT_INVALID)
                return
            username = app.storage.user.get("username")
            token = app.storage.user.get("token")
            if not username or not token:
                ui.notify(COMPOSE_LOGIN_PROMPT)
                ui.navigate.to("/login")
                return
            async with api.client() as http:
                response = await http.post(
                    f"/users/{username}/entries",
                    json={"content": content},
                    headers={"Authorization": f"Bearer {token}"},
                )
            if response.status_code == 201:
                ui.notify(SAVE_SUCCESS)
                compose.value = ""
                refreshed = await _fetch_entries(username, token)
                if refreshed.status_code == 200:
                    entry_list.refresh(refreshed.json())
            elif response.status_code == 401:
                ui.notify(COMPOSE_LOGIN_PROMPT)
                ui.navigate.to("/login")
            else:
                ui.notify(GENERIC_FAILURE)

        compose = ui.textarea(label=COMPOSE_LABEL)
        compose.props(f"maxlength={CONTENT_MAX}")
        ui.button(SAVE_CAPTION, color="high-energy-pleasant", on_click=save_entry)

        username = app.storage.user.get("username")
        token = app.storage.user.get("token")
        if not username or not token:
            entry_list([])
            return

        response = await _fetch_entries(username, token)
        if response.status_code == 200:
            entry_list(response.json())
        elif response.status_code == 401:
            ui.label(LOGIN_PROMPT)
            ui.navigate.to("/login")
        else:
            ui.label(GENERIC_FAILURE)
```

Load-bearing details:

- **`entry_list` is defined *inside* the page function, never at module
  scope.** Verified in `nicegui/functions/refreshable.py` (3.16.0): a
  `refreshable` object keeps `self.targets`, appending one target per call
  (`__call__`, lines 80-85), and `refresh()` re-runs the function for *every*
  target whose `instance` matches — and `instance` is `None` for every plain
  (non-method) function, so nothing separates one client's target from
  another's (`_execute_refresh`, lines 109-117). A module-scope `@ui.refreshable`
  would therefore make one user's save repaint **every** connected client's
  journal with the saving user's entries — a cross-session data leak, not
  just a redraw glitch. Defining it per page call gives each client its own
  object with exactly one target. `prune()` then keeps that trivially correct.
- **The list function stays synchronous and takes `entries` as a parameter;
  the fetch stays outside it.** This is FE-8a's forward pointer honoured
  literally. An `async` refreshable that fetched for itself would re-run
  FE-8a's 401/generic branches on every save (a second inline "Please log in
  to view your journal." plus a navigation, on top of the notify the save
  path already showed), or — if those branches were dropped to avoid that —
  would swallow the page-load failures that manual steps 4 and 5 exist to
  check. Fetch outside, render inside.
- **`entry_list(entries)` and `entry_list.refresh(entries)` both pass the
  argument positionally.** `_execute_refresh` re-raises a `TypeError` with
  the message "needs to be consistently passed … either as positional or as
  keyword argument" (lines 118-126) if the two call styles are mixed; and
  `target.args = args or target.args` (line 116) is what makes the refresh
  actually replace the previous list rather than re-render the stale one. Do
  not "clarify" either call into `entries=...`.
- **`entry_list.refresh(...)` is *not* awaited.** `refresh()` returns an
  `AwaitableResponse`, which schedules its fire-and-forget path as a
  background task in `__init__` and raises `RuntimeError` if awaited any
  later than immediately (`nicegui/awaitable_response.py:29-33`). Since the
  list function is synchronous, `_execute_refresh` yields no awaitables and
  the fire-and-forget path does the whole re-render on the next loop tick.
  Never bind the return value to a variable and await it afterwards.
- **The compose elements are built before the storage check, so the form
  renders for a logged-out visitor and sits above the list.** This is the
  whole automated surface of FE-8b: the `client` fixture is always a
  logged-out session, so the textarea and button must exist on that render or
  all four tests fail. It also matches `/`, where the pad and "Log this mood"
  render logged-out and short-circuit on click.
- **The logged-out branch calls `entry_list([])` rather than
  `ui.label(JOURNAL_EMPTY)` directly.** Same rendered string (the `else` arm
  emits exactly that label), so
  `test_journal_page_shows_the_empty_prompt_when_logged_out` keeps passing —
  NiceGUI serializes every element of the page into the HTML payload
  regardless of nesting, so being inside a `RefreshableContainer` does not
  hide it. Going through the refreshable keeps one construction path for the
  list instead of two that can drift apart.
- **Validation runs before the request, not after.** REQ-ENTRY-1's
  `min_length=1, max_length=5000` (`schemas.EntryBase`) means an empty or
  over-long body comes back 422, whose `detail` echoes the submitted input —
  and FE-3b's rule is that a raw response body must never reach `ui.notify`.
  Checking locally keeps that 422 path unreachable through the UI and lets
  the message name the actual rule. The generic `else` branch stays as the
  backstop, so a 422 that somehow does arrive still shows the fixed string.
- **`maxlength=5000` is belt-and-suspenders, not the guard.** It is real —
  Quasar's `useFieldProps` declares `maxlength: [Number, String]` and QInput
  binds it onto the native element it renders for `type === "textarea"` — but
  it only constrains *typing/pasting into that one field*. It does not
  survive a programmatic `compose.value = ...`, a websocket message crafted
  by hand, or the prop being dropped in a later refactor, and it cannot
  express the *stripped*-and-non-empty half of the rule at all (whitespace
  passes `maxlength` happily). So the `len(content) > CONTENT_MAX` check
  stays even though typing alone cannot trip it: it is the guard, the prop is
  the early feedback. `.props(f"maxlength={CONTENT_MAX}")` stores the value
  as the *string* `"5000"` (`Props.parse`'s unquoted branch — the same
  finding FE-6a recorded for `tabindex=0`), which is why the test compares
  `str(...)`.
- **`(compose.value or "").strip()`, not `compose.value.strip()`.** NiceGUI
  3.16.0 types `Input.value` / `Textarea.value` as `str | None` (with a
  "DEPRECATED: change to None in 4.0" comment on the `''` default), so a
  cleared field can legitimately hand back `None`. Same defensive shape
  FE-3a's register validators already use (`len(v or "")`).
- **The handler re-reads `app.storage.user` at click time** instead of
  closing over the page-level `username`/`token`. The page renders for
  logged-out visitors, so those locals are `None` on exactly the render where
  someone might log in elsewhere and come back to click Save; re-reading is
  also what `mood_pad.log_mood()` does. The names deliberately shadow the
  page-level ones — Python makes them local to `save_entry` by assignment, no
  `nonlocal`, and no path reads them before assigning.
- **Body is `{"content": content}` only** — no `timestamp` (REQ-ENTRY-2
  defaults it server-side), no `mood_id` (FE-8c). The value posted is the
  *stripped* text, i.e. what was validated, never `compose.value` re-read.
- **`_fetch_entries` is extracted because there are now two GET call sites**
  (page load and post-save refresh) in one module; leaving both inline would
  duplicate the URL, the `params=` window and the header three lines apart.
  It returns the `httpx.Response` rather than a decoded list because the page
  needs the status code to pick between three branches. `import httpx` at
  module scope is for that annotation only; the module already handles
  response objects, and `httpx` has been a direct runtime dependency since
  a585be0. Returning from inside `async with api.client()` is safe: these are
  non-streaming requests, fully read before the client closes — the same
  reason FE-7/FE-8a read `.json()` after the `with` block exits.
- **A successful save re-fetches; it does not prepend the POST's response
  body to a local list.** `POST /users/{username}/entries` does return the
  created `EntryResponse`, so a client-side prepend would save a round trip —
  but it would also mean re-implementing the server's newest-first ordering
  and the `limit=10` window in the page (`entries[:JOURNAL_LIMIT]`), which is
  exactly the client-side re-derivation FE-7 and FE-8a refused. The extra
  call is in-process ASGI, not network.
- **A failed refresh-fetch is silent.** The row specifies the three branches
  of the *POST*; the refresh GET is machinery, and its failure modes are
  already visible on the next page load. Since `ui.notify(SAVE_SUCCESS)` has
  already fired for a save that genuinely succeeded, following it with
  "Could not complete the request." would misreport the outcome. So the
  refresh happens only on 200 and the stale list is left alone otherwise —
  a design call made here, not something TASKS.md's row enumerates.
- **Constants, not literals, for the two login prompts** — `LOGIN_PROMPT`
  (view, page-load 401) and `COMPOSE_LOGIN_PROMPT` (write, save 401) are
  different strings by requirement and sit next to each other on purpose;
  the trailing comments are there so neither gets "unified" into the other.
  `LOGIN_PROMPT` keeps its FE-8a name so the diff stays additive.

#### Open UX details, deliberately not designed around

- **Nothing disables the button while the POST is in flight**, so a fast
  double-click can create two entries. FE-5 recorded the same gap for "Log
  this mood" and listed the fix as out of scope; FE-8b keeps that posture
  rather than inventing a debounce the row does not ask for. If it matters,
  it is one new requirement covering both buttons.
- **FE-8a's newline-collapse note gets its first real exposure here.** A
  `ui.textarea` makes multi-line entries the common case, and `ui.label`
  renders with default `white-space: normal`, so they display as one
  paragraph. Manual step 1 is where this becomes visible. Still a new
  requirement (one `.style("white-space: pre-wrap")` call), not a silent
  amendment.

#### Note for FE-12

`journal.py` now has **two** `f"Bearer {token}"` sites (`_fetch_entries` and
`save_entry`), so FE-12's `api.auth_headers(token)` extraction covers four
call sites across three modules rather than three. FE-8b still writes them
inline for the same reason FE-8a did: a cross-module refactor does not belong
in the commit that adds a feature.

Out of scope, deliberately: linking a mood to the entry and rendering linked
moods (FE-8c — its `ui.select` goes next to `compose`, and its `mood_id` key
into this POST body); editing or deleting an entry; disabling the button
during the request; pagination/"load more"; any auth guard on `/journal`; any
change to `frontend/api.py`, `frontend/history.py`, `frontend/mood_pad.py`,
`frontend/__init__.py`, `app.py` or the REST layer.

**Traceability:** FE-8b → the `entry_list()` `@ui.refreshable` and the
`save_entry()` closure inside `frontend.journal.create()`'s `journal()` page,
the `ui.textarea(label="New journal entry")` / `ui.button("Save entry", …)`
pair that precedes them in the DOM, and the module-level
`_fetch_entries()` helper — all in `backend/app/frontend/journal.py`.
Requirement: `TASKS.md`'s **FE-8b** row (epic "NiceGUI frontend redesign").
Split in two, the same shape as FE-5/FE-7/FE-8a.

**Automated slice** — four tests, all with the plain (logged-out) `client`
fixture, in `backend/app/tests/test_frontend.py`:

- `test_journal_page_renders_the_compose_textarea` — an element on
  `GET /journal` carries `label="New journal entry"` **and**
  `type="textarea"`, the discriminator that separates `ui.textarea` from
  `ui.input` (`Textarea.__init__` sets `_props['type'] = 'textarea'`).
- `test_journal_compose_textarea_caps_input_at_5000_characters` — that same
  element's `maxlength` prop stringifies to `"5000"`.
- `test_journal_page_renders_the_save_entry_button` — an element is labelled
  `"Save entry"`.
- `test_journal_save_entry_button_uses_high_energy_pleasant` — that same
  element carries `color="high-energy-pleasant"` (hyphenated, per FE-3a:
  an underscored name degrades to an inline style and the prop vanishes).

No new `tests/test_journal.py`: FE-8b adds no pure function (`save_entry`
and `entry_list` are closures that touch the network and the DOM, and
`_fetch_entries` is one HTTP call). The first unit tests for this module
still land with FE-8c. `POST /users/{username}/entries` is already covered by
`tests/test_entries.py` (REQ-ENTRY-1/3) — do not re-test it through the UI,
and do not reach for the banned NiceGUI fixtures to drive the click path.

**Manual slice** (dev server from `backend/app/`, per the Testing policy; all
five required, result recorded in the commit message):

1. *Save success* — logged in on `/journal`, type a multi-line entry, click
   "Save entry", and confirm: the notification "Journal entry saved!", the
   textarea goes empty, and the new entry appears as the **top card without a
   page reload**, its timestamp formatted `2026-08-27 14:05 UTC`. With ten or
   more prior entries, confirm the list still shows exactly ten cards after
   the refresh (i.e. the oldest dropped off).
2. *Empty-content validation* — with the textarea empty, and again with only
   spaces/newlines in it, click "Save entry" and confirm the notification
   "Journal entry must be between 1 and 5000 characters.", that the list does
   not change, and — in the browser's network tab or the server log — that
   **no `POST /users/{username}/entries` was sent at all**. Also confirm the
   field refuses to accept a 5001st character when pasting a long text.
3. *Logged out* — in a fresh private window (no `app.storage.user` entries),
   confirm the textarea and "Save entry" button are visible alongside "No
   journal entries yet.", then type something and click: notification "Please
   log in to write a journal entry." and navigation to `/login`, with no
   request sent.
4. *Expired/invalid token* — set `token` in
   `backend/app/.nicegui/storage-user-*.json` to a garbage string, reload
   `/journal` (which will show FE-8a's page-load 401 path), then from a
   session where the page rendered, click "Save entry" with real content and
   confirm the same "Please log in to write a journal entry." notification
   and redirect — this exercises the response branch where step 3 exercises
   the short-circuit.
5. *Reload persistence* — after step 1, hard-reload `/journal` and confirm
   the saved entry is still the top card with identical text (whitespace
   stripped at the ends, interior text untouched), proving the refresh
   rendered what the API actually stored rather than a client-side echo.

Worth eyeballing during step 1: the compose form sits **above** the list, and
the "No journal entries yet." string is unchanged for a fresh user with the
form present.

### FE-8c — Linking and displaying a mood on `/journal`

No new component and **no new file**: `backend/app/frontend/journal.py` is again
the only file that changes. `frontend/__init__.py`, `frontend/api.py`,
`frontend/history.py`, `frontend/mood_pad.py`, `app.py`, the REST layer and
`pyproject.toml` are untouched, and FE-8a's three plus FE-8b's four
`test_frontend.py` tests keep passing unchanged — `JOURNAL_EMPTY`,
`COMPOSE_LABEL`, `SAVE_CAPTION`, the `maxlength` prop and the unguarded
`/journal` route are all left byte-identical.

This item closes REQ-ENTRY-5's client half. Everything FE-8a and FE-8b settled
(reading `app.storage.user` before the first `await`, inline `ui.label` for
page-load failures vs. `ui.notify` for action failures, status-code-first and
body-never, `params=` rather than a hand-built query string, `f"Bearer {token}"`
inline pending FE-12, `@ui.refreshable` defined per page call) applies unchanged
and is not restated. What is new is a **second GET on the page-load path**, a
`ui.select` that is built empty and populated afterwards, one extra key in the
POST body, and one extra conditional label per card.

#### The module, literally (the whole updated `frontend/journal.py`)

```python
"""The journal entries page, at /journal.

See ARCHITECTURE.md's FE-8a entry for the read-only listing, FE-8b's for
the compose form, and FE-8c's for mood linking: why entry_list is defined
inside the page function rather than at module scope, why validation runs
before the request, why a successful save re-fetches the list instead of
prepending the POST's own response body, and why the mood select is built
empty and repopulated after the fetch rather than built once the moods are
known.
"""

from datetime import datetime

import httpx
from nicegui import app, ui

from . import api
from .history import quadrant_label

JOURNAL_EMPTY = "No journal entries yet."
LOGIN_PROMPT = "Please log in to view your journal."  # page-load 401
COMPOSE_LOGIN_PROMPT = "Please log in to write a journal entry."  # save 401
GENERIC_FAILURE = "Could not complete the request."
SAVE_SUCCESS = "Journal entry saved!"
CONTENT_INVALID = "Journal entry must be between 1 and 5000 characters."
COMPOSE_LABEL = "New journal entry"
SAVE_CAPTION = "Save entry"
MOOD_SELECT_LABEL = "Link a mood"
NO_MOOD_OPTION = "No linked mood"
CONTENT_MAX = 5000
JOURNAL_LIMIT = 10
MOOD_WINDOW = 100


def _format_timestamp(raw: str) -> str:
    """Render an EntryResponse's naive-UTC ISO timestamp as ``%Y-%m-%d %H:%M UTC``."""
    return datetime.fromisoformat(raw).strftime("%Y-%m-%d %H:%M UTC")


def mood_option_label(mood: dict) -> str:
    """Caption one mood in the "Link a mood" select: timestamp, em dash, quadrant."""
    return (
        f"{_format_timestamp(mood['timestamp'])} — "
        f"{quadrant_label(mood['energy'], mood['valence'])}"
    )


def mood_line(mood: dict | None) -> str:
    """Render an entry's linked mood as one card line; "" when nothing is linked."""
    if mood is None:
        return ""
    energy = mood["energy"]
    valence = mood["valence"]
    return (
        f"Mood: {quadrant_label(energy, valence)} "
        f"(Energy: {energy:.2f} · Valence: {valence:.2f})"
    )


def _mood_options(moods: dict[int, dict]) -> dict:
    """Build the select's ``{value: caption}`` map, with the ``None`` option first."""
    options: dict = {None: NO_MOOD_OPTION}
    options.update({mood_id: mood_option_label(mood) for mood_id, mood in moods.items()})
    return options


async def _fetch_entries(username: str, token: str) -> httpx.Response:
    """GET the newest ``JOURNAL_LIMIT`` journal entries for ``username``."""
    async with api.client() as http:
        return await http.get(
            f"/users/{username}/entries",
            params={"limit": JOURNAL_LIMIT},
            headers={"Authorization": f"Bearer {token}"},
        )


async def _fetch_moods(username: str, token: str) -> httpx.Response:
    """GET the newest ``MOOD_WINDOW`` moods for ``username``, for linking and display."""
    async with api.client() as http:
        return await http.get(
            f"/users/{username}/moods",
            params={"limit": MOOD_WINDOW},
            headers={"Authorization": f"Bearer {token}"},
        )


def create() -> None:
    """Register the /journal page."""

    @ui.page("/journal", title="Journal")
    async def journal() -> None:
        @ui.refreshable
        def entry_list(entries: list[dict], moods: dict[int, dict]) -> None:
            if entries:
                with ui.column():
                    for entry in entries:
                        with ui.card():
                            ui.label(_format_timestamp(entry["timestamp"]))
                            ui.label(entry["content"])
                            line = mood_line(moods.get(entry.get("mood_id")))
                            if line:
                                ui.label(line)
            else:
                ui.label(JOURNAL_EMPTY)

        async def save_entry() -> None:
            content = (compose.value or "").strip()
            if not content or len(content) > CONTENT_MAX:
                ui.notify(CONTENT_INVALID)
                return
            username = app.storage.user.get("username")
            token = app.storage.user.get("token")
            if not username or not token:
                ui.notify(COMPOSE_LOGIN_PROMPT)
                ui.navigate.to("/login")
                return
            payload: dict = {"content": content}
            if mood_select.value is not None:
                payload["mood_id"] = mood_select.value
            async with api.client() as http:
                response = await http.post(
                    f"/users/{username}/entries",
                    json=payload,
                    headers={"Authorization": f"Bearer {token}"},
                )
            if response.status_code == 201:
                ui.notify(SAVE_SUCCESS)
                compose.value = ""
                mood_select.value = None
                refreshed = await _fetch_entries(username, token)
                if refreshed.status_code == 200:
                    entry_list.refresh(refreshed.json(), moods)
            elif response.status_code == 401:
                ui.notify(COMPOSE_LOGIN_PROMPT)
                ui.navigate.to("/login")
            else:
                ui.notify(GENERIC_FAILURE)

        compose = ui.textarea(label=COMPOSE_LABEL)
        compose.props(f"maxlength={CONTENT_MAX}")
        mood_select = ui.select(_mood_options({}), label=MOOD_SELECT_LABEL, value=None)
        ui.button(SAVE_CAPTION, color="high-energy-pleasant", on_click=save_entry)

        moods: dict[int, dict] = {}
        username = app.storage.user.get("username")
        token = app.storage.user.get("token")
        if not username or not token:
            entry_list([], moods)
            return

        response = await _fetch_entries(username, token)
        if response.status_code == 200:
            mood_response = await _fetch_moods(username, token)
            if mood_response.status_code == 200:
                moods = {mood["id"]: mood for mood in mood_response.json()}
                mood_select.set_options(_mood_options(moods))
            entry_list(response.json(), moods)
        elif response.status_code == 401:
            ui.label(LOGIN_PROMPT)
            ui.navigate.to("/login")
        else:
            ui.label(GENERIC_FAILURE)
```

Load-bearing details:

- **The moods fetch is nested inside the entries fetch's `200` branch**, not
  run alongside it. The row is explicit — "and only then". If the entries call
  401s or 403s, the page has already committed to `LOGIN_PROMPT` /
  `GENERIC_FAILURE` and (for 401) a navigation; a second call from there would
  be a wasted round trip whose own failure branch would have to be suppressed
  anyway. Sequential, not `asyncio.gather`: the second call is only meaningful
  once the first succeeded, and both are in-process ASGI calls against sync
  `def` endpoints (`get_entries` at `app.py:534`, `get_moods` at `app.py:300`),
  which FastAPI runs in the threadpool, so two of them stay comfortably inside
  NiceGUI's 3 s `response_timeout` (FE-7's finding).
- **`MOOD_WINDOW = 100` is the endpoint's own default** — `get_moods` declares
  `limit: int = 100` with no upper bound (read from `app.py:300-303`, not
  recalled), so `params={"limit": MOOD_WINDOW}` is a no-op restatement that
  documents the window at the call site instead of relying on a server default
  that could change. It is deliberately *not* `history.HISTORY_LIMIT` (10):
  that constant sizes a display table, this one sizes a lookup index, and
  coupling them would silently shrink the linkable set to ten moods.
- **The select is created empty, then repopulated with `set_options`.** It has
  to be: FE-8b's rule is that the compose elements are built *before* the
  storage check so a logged-out visitor sees the form and the form sits above
  the list in the DOM — but the moods are only known after two awaits that a
  logged-out visitor never reaches. Building the select after the fetch would
  put it below the list and omit it entirely when logged out. All of this runs
  inside the page-building coroutine, before the page's HTML is serialized, so
  the populated options are in the *initial* render — there is no flicker and
  no second paint.
- **`_mood_options()` is the single construction path**, used for both the
  empty select and the repopulated one, so the `None` option can never be
  missing from one of them. It must stay first in the dict:
  `ChoiceElement._update_values_and_labels` (nicegui 3.16.0,
  `elements/choice_element.py:40-42`) takes `list(options.keys())` in insertion
  order and `_update_options` renders `{'value': <index>, 'label': ...}` pairs
  from it, so "No linked mood" being key `None` inserted first is what makes it
  option zero.
- **`value=None` is passed explicitly and is a real option, not an absence.**
  `ChoiceElement.__init__`'s guard is `value is not None and value not in
  self._values`, so `None` never raises regardless of the options — but
  `Select._value_to_model_value` does `self._values.index(value)` and returns
  `None` on `ValueError`, i.e. a select whose options did *not* contain the
  `None` key would render with a **blank** display rather than the "No linked
  mood" caption the row requires. Passing it explicitly also sidesteps
  `resolve_defaults`: the parameter's declared default is
  `DEFAULT_PROPS['model-value'] | None`, a sentinel that a future
  `ui.select.default_props('model-value', ...)` could redirect; an explicit
  argument is not a sentinel and is used as-is (`defaults.py:53-64`).
- **`mood_select.value` is the mood's `id` or `None`, never a caption or an
  index.** `Select._event_args_to_value` maps the browser's
  `e.args['value']` index back through `self._values`, which are the dict's
  *keys* (`elements/select.py:113-121`). That is why the options dict is keyed
  by `mood["id"]` and why `save_entry` can use the value directly.
- **`mood_id` is added to the body or omitted entirely — never sent as
  `null`.** `if mood_select.value is not None: payload["mood_id"] = ...`. Both
  forms happen to behave identically server-side today (`EntryCreate.mood_id`
  is `int | None = None`, and `create_entry` only validates ownership `if
  entry.mood_id is not None`, `app.py:507-517`), but the row specifies
  omission, and building the dict conditionally is what keeps a future
  `model_config` change or a stricter schema from turning an unlinked entry
  into a 422. Note the ownership check: a `mood_id` the user does not own comes
  back **404**, which lands in `save_entry`'s generic `else` branch — correct,
  and unreachable from the UI since every option came from that user's own
  moods.
- **A successful save resets the select to `None` alongside clearing the
  textarea.** The row does not enumerate this (it names only the textarea
  clear, inherited from FE-8b) — it is a design call made here, on the same
  footing as FE-8b's "a failed refresh-fetch is silent". Without it, the next
  entry silently inherits the previous entry's mood link, which is a data
  error the user has no visual cue for once the notification fades. Setting
  `.value = None` is safe because `None` is a key of the options dict, so the
  display returns to "No linked mood" rather than going blank.
- **No moods re-fetch after a save.** Saving a journal entry cannot create a
  mood, so the index is still current; `entry_list.refresh(refreshed.json(),
  moods)` reuses the dict built at page load. Consequence, accepted: a mood
  logged in another tab after this page loaded is not in the select until
  reload. One more round trip per save to fix a case the row does not mention
  is not worth it.
- **`entry_list` takes two positional parameters and every call site passes
  both positionally.** `_execute_refresh` re-raises a `TypeError` if the
  initial call and `refresh()` mix positional and keyword styles, and
  `target.args = args or target.args` is what makes the refresh render the new
  data (FE-8b's finding). `entry_list([], moods)`, `entry_list(entries,
  moods)`, `entry_list.refresh(refreshed.json(), moods)` — three call sites,
  one style.
- **`moods` is rebound in the page function and only *read* by the closures.**
  `save_entry` and `entry_list` resolve it at call time, so the rebinding after
  the fetch is visible to both; the `moods: dict[int, dict] = {}` initializer
  before the storage check is what keeps the logged-out `entry_list([], moods)`
  call and any click that follows it from hitting a `NameError`. Do not add an
  assignment to `moods` inside `save_entry` — Python would make it local there
  and break the read (the same shadowing mechanic FE-8b relies on deliberately
  for `username`/`token`).
- **The third label is created only when `mood_line` returns a non-empty
  string**, inside the card, after content. `moods.get(entry.get("mood_id"))`
  collapses all three "no mood line" cases into one lookup: `mood_id` is
  `null` (never linked, or unlinked by REQ-ENTRY-6's mood deletion, which nulls
  the FK rather than cascading), or `mood_id` is set but outside the 100-mood
  window (`.get` returns `None`). `moods.get(None)` is `None` because the raw
  index — unlike `_mood_options`'s output — has no `None` key. FE-8a's "exactly
  two labels, timestamp first" contract is what makes appending this third one
  land at the bottom of the card rather than in the middle.
- **`quadrant_label` is imported from `frontend/history.py`, not copied.**
  `frontend/__init__.py`'s docstring forbids importing `models`, `database`,
  `auth` and `analytics` — a sibling import inside the `frontend` package is
  not that, and there is no cycle (`history.py` imports only `api`). See the
  flag below on why `_format_timestamp` nonetheless stays duplicated.
- **Both non-ASCII separators are load-bearing and pinned by tests**: the em
  dash `—` (U+2014) in `mood_option_label`, the middle dot `·` (U+00B7) in
  `mood_line`, the latter matching `mood_pad._readout`'s existing
  `f"Energy: {energy:.2f} · Valence: {valence:.2f}"`. Do not "normalize" either
  to a hyphen or a pipe. Both f-strings are split across two implicitly
  concatenated lines because a single line lands at exactly the 100-character
  `line-length` limit — splitting keeps `ruff format` from having an opinion.
- **`{value:.2f}` rounds, it does not truncate** — `0.666` renders `0.67`,
  which two of the unit tests pin. Latent cosmetic edge: a value in
  `(-0.005, 0)` renders `-0.00`. Unreachable in practice (the pad rounds to two
  decimals before POSTing, per FE-6a's `nudge`), so it is noted, not designed
  around.

#### One helper imported, one still duplicated — deliberate, and worth a look

FE-8a's entry argued that if `_format_timestamp` were ever pulled out, the home
should be a shared `frontend/format.py`, "not `history.py` (journal importing
display helpers *from the history page module* would invert the dependency
between two sibling pages)". FE-8c's row nonetheless mandates exactly that
import for `quadrant_label`, so `journal.py` now depends on `history.py` while
still keeping its own copy of `_format_timestamp`. The asymmetry is real but
defensible: `quadrant_label` is public, non-trivial (five branches and a
neutral band that must not drift from `analytics.get_mood_quadrant_name`), and
pinned by `tests/test_history.py`, so a second copy would be a genuine
correctness risk; `_format_timestamp` is a private two-liner, and importing an
`_`-prefixed name across modules is worse than duplicating it. The consequence
to record: `frontend.journal → frontend.history` is now a live edge between two
page modules. If a third page needs either helper — or if that edge starts
carrying anything else — the answer is `frontend/format.py` holding both
`quadrant_label` and `format_timestamp`, with `history.py` and `journal.py`
importing from it. That refactor is not in FE-8c's row and is not bundled here.

#### Known limitation, accepted by the requirement

**A mood older than the user's newest 100 renders no mood line, silently.** The
page pairs a 10-entry window with a 100-mood window, so this needs a user who
logged 100+ moods *after* the mood in question while writing 10 or fewer
journal entries. The alternatives are worse: an N+1
`GET /users/{u}/moods/{mood_id}` per card (explicitly out of scope in FE-8a and
here), or a wider window that grows the page payload for every visitor. If it
ever bites, the fix is a server-side change — embedding the mood in
`EntryResponse` — which is a new requirement against the REST layer, not a
frontend patch.

#### Graceful degradation, and why it shows nothing

If the entries fetch succeeded but the moods fetch returns non-2xx, the page
renders the list with no mood lines and a select holding only "No linked mood",
and says nothing. That is the row's wording and it is right: the user asked to
see their journal, and they are seeing it; a "Could not complete the request."
banner over a correctly rendered list would misreport the outcome the same way
FE-8b's silent refresh failure would have. The degraded state is also
self-describing — an empty mood dropdown is visibly not a working dropdown.
Note that this branch is nearly unreachable in practice, since both calls use
the same username and token against the same in-process API; the realistic
trigger is a 30-minute token expiring *between* the two awaits.

#### Note for FE-12

`journal.py` now has **three** `f"Bearer {token}"` sites (`_fetch_entries`,
`_fetch_moods`, `save_entry`), so FE-12's `api.auth_headers(token)` extraction
covers five call sites across three modules. Still written inline here for the
same reason as FE-8a/FE-8b.

Second, smaller trigger worth recording: `GET /users/{u}/moods` now has **two**
call sites in two page modules (`history.history()` and
`journal._fetch_moods()`), with different windows. That is two, not three, and
the two windows differ in purpose, so nothing is extracted now — but if a third
page needs moods, the extraction is an `api.get_moods(username, token, limit)`
helper in `frontend/api.py`, *not* an import from `history.py`.

Out of scope, deliberately: changing or removing an existing entry's mood link
after it is saved; unlinking from the UI; any per-entry
`GET /users/{u}/moods/{mood_id}` fetch; widening `JOURNAL_LIMIT`;
re-fetching moods after a save; editing or deleting an entry; disabling the
button during the request; pagination/"load more"; any auth guard on
`/journal`; any change to `frontend/api.py`, `frontend/history.py`,
`frontend/mood_pad.py`, `frontend/__init__.py`, `app.py` or the REST layer.

**Traceability:** FE-8c → the public `mood_option_label()` and `mood_line()`
functions, the private `_mood_options()` helper and the `_fetch_moods()`
coroutine at module scope in `backend/app/frontend/journal.py`, plus, inside
`frontend.journal.create()`'s `journal()` page, the
`ui.select(label="Link a mood")` between the textarea and the Save button, the
conditional third `ui.label` in `entry_list()`, and the conditional
`"mood_id"` key in `save_entry()`'s POST body. Requirement: `TASKS.md`'s
**FE-8c** row (epic "NiceGUI frontend redesign"), closing REQ-ENTRY-5's client
half. Third and final part of the FE-8 split.

**Automated slice** — exactly the six unit tests already written (and confirmed
red with `ImportError`) in `backend/app/tests/test_journal.py`, the first tests
this module has:

- `test_mood_line_is_empty_when_no_mood_is_linked` — `None` → `""`, which is
  what makes the third label conditional rather than blank-but-present.
- `test_mood_line_names_the_quadrant_and_both_coordinates` — the exact string
  `"Mood: High Energy Pleasant (Energy: 0.80 · Valence: 0.60)"`.
- `test_mood_line_calls_a_near_origin_mood_neutral` — `(0.05, -0.05)` reads
  `"Neutral"`, pinning the delegation to `quadrant_label`'s neutral band rather
  than a re-derived one.
- `test_mood_line_pads_coordinates_to_two_decimals` and
  `test_mood_line_rounds_coordinates_to_two_decimals` — `0.5` → `0.50`,
  `0.666` → `0.67`.
- `test_mood_option_label_joins_the_formatted_timestamp_and_quadrant` — the
  exact string `"2026-08-27 09:00 UTC — High Energy Pleasant"`.

**No new `test_frontend.py` test in this item.** A `client`-fixture assertion
that `GET /journal` renders `label="Link a mood"` would be legitimate and cheap
(FE-8b's textarea test in miniature), but the accepted row's verification slice
is the unit tests plus manual acceptance, and adding a seventh test now would
mean writing it outside the red-green gate. `POST /users/{u}/entries` with a
`mood_id`, including the 404-on-someone-else's-mood path, is already covered by
`tests/test_entries.py` (REQ-ENTRY-5) — do not re-test it through the UI, and
do not reach for the banned NiceGUI fixtures to drive the select.

**Manual slice** (dev server from `backend/app/`, per the Testing policy; all
five required, result recorded in the commit message):

1. *Select population* — logged in with at least three moods logged from `/`,
   open `/journal` and open the "Link a mood" dropdown. Confirm: the field
   shows **"No linked mood"** before it is touched; that same entry is the
   first option; below it, one option per mood, **newest first**, each reading
   like `2026-08-27 09:00 UTC — High Energy Pleasant`. Log one mood at the pad's
   untouched origin first and confirm its option reads `— Neutral`, not a
   quadrant name.
2. *`mood_id` reaches the POST body* — pick a mood, type content, click "Save
   entry", and confirm in the browser's network tab that the request body is
   `{"content": "…", "mood_id": <that mood's id>}`; the new top card shows a
   **third** line `Mood: <quadrant> (Energy: 0.42 · Valence: -0.13)` matching
   the mood picked; and the select has snapped back to "No linked mood".
3. *Omission, not `null`* — immediately save a second entry **without** touching
   the select, and confirm the network tab shows a body of `{"content": "…"}`
   with **no `mood_id` key at all** (not `"mood_id": null`), and that the new
   card has exactly two labels.
4. *Null and outside-window cases* — hard-reload `/journal` and confirm the
   linked entry from step 2 still shows its third line (i.e. it came from the
   API, not from client state). Then delete that mood via `/docs`
   (`DELETE /users/{username}/moods/{mood_id}`, which nulls `mood_id` per
   REQ-ENTRY-6 rather than deleting the entry), reload, and confirm the entry is
   still listed with **two** labels, no third line, no error message, and no
   traceback in the server log.
5. *Degradation branch* — temporarily set `MOOD_WINDOW = "abc"` in
   `frontend/journal.py` so the moods fetch alone comes back 422 while the
   entries fetch still succeeds. Reload `/journal` and confirm: the entry cards
   render normally **with no mood lines at all**, the select offers only "No
   linked mood", and **no** error message appears anywhere on the page. Restore
   `MOOD_WINDOW = 100` before staging anything.

Worth eyeballing during step 1: the select sits **between** the textarea and
the "Save entry" button, and in a fresh private window (logged out) `/journal`
still shows the textarea, the select with its single "No linked mood" option,
the button, and "No journal entries yet.".
