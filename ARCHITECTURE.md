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
