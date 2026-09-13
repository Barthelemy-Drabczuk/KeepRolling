# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Moodometer: a FastAPI + PostgreSQL mood-tracking app built on the circumplex
model of affect (energy × valence). Users log moods on a 2D grid and add
journal entries; the API also computes statistics/patterns/insights and
exports data as CSV/JSON/PDF.

## Commands

The project is managed with **pixi** (`pyproject.toml` → `[tool.pixi.tasks]`).
Linting/formatting (`ruff`) live in the `dev` feature/environment, so use
`pixi run -e dev ...` for those two, and plain `pixi run ...` for the rest:

```bash
pixi run -e test test           # pytest (needs -e test: pytest lives in the test feature, not default)
pixi run -e dev lint            # ruff check .
pixi run -e dev format-check    # ruff format --check .
pixi run -e dev format          # ruff format . (auto-fixes formatting)
pixi run db-test                # sanity-check the DB connection (src/backend/db.py)
pixi run db-migrate             # alembic upgrade head
pixi run db-revision -m "message"   # alembic revision --autogenerate
```

**Running the dev server — do not use `pixi run dev` as-is.** That task runs
`uvicorn src.backend.app.app:app` from the repo root, but every module in
`src/backend/app/` uses bare imports (`from database import get_db`, `from models
import ...`), and `app.mount("/static", StaticFiles(directory="static"))`
uses a relative path too. Both only resolve if `src/backend/app/` itself is the
process's working directory / on `sys.path`. This has been verified: running
from repo root fails with `ModuleNotFoundError: No module named 'database'`.
Instead:

```bash
cd src/backend/app
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Tests live in `src/backend/app/tests/`; `src/backend/app/pytest.ini` sets
`pythonpath = . ../../` (the second entry puts `src/` on the path too, for
`from frontend.history import ...` — `src/frontend/` is a sibling of
`src/backend/`, not nested inside it) so `pytest`, run from
`src/backend/app/`, can import the application modules the same way
`uvicorn` does. Run a single file or test the normal pytest way:
`pixi run -e test pytest tests/test_auth.py` or
`pixi run -e test pytest tests/test_auth.py::test_login_succeeds`.
`tests/conftest.py` overrides the `get_db` dependency with an isolated
in-memory SQLite database per test (via the `client` fixture) and no-ops
`init_db`, so the suite never touches the real `DATABASE_URL`.

### Docker

```bash
cd src/backend
docker-compose up --build
```

Runs the `web` (FastAPI, port 8000) and `db` (Postgres 16, port 5432)
services; `web` waits for `db`'s healthcheck. `docker-compose.yml` also
bind-mounts `./alembic` and `./alembic.ini` into the container.

### Environment

`src/backend/app/.env` (gitignored) must define `DATABASE_URL`; `database.py`
raises at import time if it's unset. `auth.py` reads `SECRET_KEY` (defaults
to an insecure placeholder if unset — always set it), `ALGORITHM`
(`HS256`), and hardcodes `ACCESS_TOKEN_EXPIRE_MINUTES = 30`. `app.py`'s
frontend-mounting block (see "Frontend" below) reads `NICEGUI_STORAGE_SECRET`
the same way — also defaults to an insecure placeholder if unset, also
always set it — since it encrypts `app.storage.user`, which is where the
frontend keeps each logged-in user's JWT.

## Coding style

Follow PEP 8. `ruff` (configured in `pyproject.toml`'s `[tool.ruff]`,
`E`/`F`/`W`/`I` rules) is the enforcement mechanism — run
`pixi run -e dev lint` and `pixi run -e dev format-check` before treating
work as done; `pixi run -e dev format` auto-fixes formatting. The existing
codebase is not yet clean (mostly trailing whitespace and import
ordering — `pixi run -e dev lint` currently reports ~320 issues, largely
in `src/backend/db.py` and files ruff hasn't touched yet); don't take existing
code as a style example, and don't take on a repo-wide reformat as a side
effect of an unrelated change — fix style in files you're already editing
for another reason. `app_new.py` is excluded from ruff (see "dead code"
below) so it doesn't count toward this.

Beyond PEP 8 itself: this codebase consistently uses type hints on
function signatures (see `auth.py`, `analytics.py`) — match that in new
code — and Pydantic v2 style (`ConfigDict`, `Field(...)`) rather than v1
(`class Config`, `Field(...)` with a `Config` inner class).

## Requirements

Project requirements live in `BUSINESS.md`, one `REQ-<AREA>-<N>` per
testable statement. Before turning a requirement into tests (the
`requirement-specialist` subagent's job), it must be well-formed per
INCOSE: necessary, appropriate, unambiguous, complete, singular,
feasible, verifiable, correct, conforming. Concretely: one testable
statement per requirement (no "and"/"or" joining distinct behaviors), no
vague/subjective qualifier ("fast", "user-friendly", "robust") without a
measurable definition, no open TBD, and no requirement that can
reasonably be read two different ways. A requirement that fails one of
these gets sent back for disambiguation rather than guessed at — see
`BUSINESS.md`'s "Open questions" section for requirements currently
blocked on exactly this.

## Dependency changes

Before adding a dependency to `pyproject.toml`, bumping one, or writing
code against a dependency API not already verified earlier in the same
session, confirm the current API shape via the `context7` MCP tools
instead of assuming from memory — see the
`checking-dependencies-with-context7` skill. This matters most for
SQLAlchemy (1.x vs. 2.0 query style) and Pydantic (v1 vs. v2 validator/
config style), where both major versions are common in training data and
using the wrong one won't always fail loudly.

## Commit conventions

Imperative mood, describes the one change accurately. No
"Co-Authored-By" line, no "Generated with Claude Code" line, and no other
Anthropic/Claude.ai attribution anywhere in the message — non-negotiable.
One logical change per commit; split up anything mixed rather than
bundling it.

## Architecture

### Runtime app vs. dead code — read this before editing

- **`src/backend/app/app.py`** is the actual application (mounted by the
  Dockerfile's `CMD` and the README's run instructions) — FastAPI routes for
  auth, users, moods, entries, analytics, and export.
- **`src/backend/app/app_new.py`** is an earlier, orphaned variant of
  `app.py` (missing the export endpoints). Nothing imports or references
  it — it isn't wired into the Dockerfile, docker-compose, or any
  entrypoint. Treat it as dead unless told otherwise; don't assume changes
  to `app.py` need mirroring there. Its counterpart, `index_new.html`, no
  longer exists — it was removed along with `index.html` itself when
  NiceGUI replaced the vanilla-JS SPA (see "Frontend" below).
- **`src/backend/app/User.py`** is a standalone in-memory `User` class
  (plaintext password, dict-based mood/entry storage) that nothing else in
  the codebase imports. It predates the SQLAlchemy models and is not part of
  the request path — don't confuse it with `models.UserModel`.

### Request flow (the real path)

`app.py` wires together four modules, each with a single responsibility:

- **`database.py`** — SQLAlchemy engine/session setup from `DATABASE_URL`,
  plus the `get_db()` FastAPI dependency and `init_db()` (called on the
  `startup` event to create tables — there's no separate seed/init script;
  schema also evolves via Alembic migrations in `src/backend/alembic/versions/`
  — hand-written, not `--autogenerate`d, since there's no live Postgres to
  diff against in a typical dev/CI environment here; each has been verified
  by applying it to a real Postgres via `docker-compose up -d db`).
- **`models.py`** — the three tables: `UserModel` 1—N `MoodModel` and 1—N
  `EntryModel` (both `cascade="all, delete-orphan"`). `MoodModel.energy` and
  `.valence` are floats constrained to **-1.0..1.0** (low↔high energy,
  unpleasant↔pleasant valence) — this is the actual constraint, independent
  of the README's mention of the six-zone circumplex labels. `MoodModel` has
  an optional `notes` field (≤1000 chars); `EntryModel` has an optional
  `mood_id` FK linking a journal entry to one of the same user's moods —
  deleting a linked mood nulls out `mood_id` on referencing entries rather
  than failing or cascading (see `delete_mood` in `app.py`).
- **`schemas.py`** — Pydantic request/response models, enforcing the same
  -1.0..1.0 range plus field-length limits (username 3-50 chars, password
  min 8 chars, journal content 1-5000 chars, mood notes 1000 chars).
- **`auth.py`** — bcrypt password hashing (72-byte truncation) and JWT
  issuance/validation. `get_current_active_user` is the dependency every
  protected route uses; `app.py` additionally re-checks
  `current_user.username == username` on every per-user route, since JWT
  auth alone doesn't scope access to the path's `{username}`.
- **`analytics.py`** — pure query/stat functions (`calculate_mood_statistics`,
  `detect_mood_patterns`, `generate_insights`, quadrant distribution) called
  lazily inside the analytics/export endpoints of `app.py` rather than
  imported at module load time.

Every mutating endpoint in `app.py` follows the same shape: authenticate →
confirm `current_user.username == {username}` (403 if not) → look up the
user (404 if missing) → look up the child resource by id scoped to that user
(404 if missing) → mutate. When adding endpoints, match this order so
authorization checks stay ahead of existence checks. `GET /users/{username}`
is the one exception worth knowing about: it requires authentication but
*not* that the caller matches `{username}` — any authenticated user can look
up any other user's basic profile. That's deliberate (see `BUSINESS.md`'s
REQ-USER-6) and distinct from `GET /users/{username}/full`, which is
self-only.

### Frontend

`src/frontend/` is a NiceGUI multi-page app, a sibling of `src/backend/`
rather than nested inside it, mounted onto the same FastAPI `app` instance
at the end of `app.py` via `frontend.configure_theme()`,
`frontend.create_pages()`, then
`ui.run_with(app, mount_path="/", storage_secret=STORAGE_SECRET)`. The old
vanilla-JS SPA (`index.html`/`static/app.js`/`static/style.css`) is gone —
removed when NiceGUI was wired in.

One module per page, each with a `create() -> None` that registers its
`@ui.page`(s), called from `frontend/__init__.py`'s `create_pages()`
(explicit calls, not import-time `@ui.page` decorators — NiceGUI's test
fixtures re-`exec` `app.py` per test via `runpy`, and Python's module
cache means decorators wouldn't re-register on a second run):
`auth.py` (`/login`, `/register`), `mood_pad.py` (`/`, the circumplex
pad plus nav links to every other page), `history.py` (`/history`),
`journal.py` (`/journal`), `analytics.py` (`/analytics`), and
`export.py` (`/export`). `frontend/api.py` isn't a page — it's the shared
HTTP transport every authenticated page calls through: `client()` returns
an `httpx.AsyncClient` wired to the same FastAPI `app` via in-process
ASGI transport (not a real network round trip), and `auth_headers(token)`
builds the `Authorization: Bearer …` header. `frontend/__init__.py` also
holds `QUADRANT_COLOURS` (the four circumplex-quadrant hex colours, shared
by `configure_theme()`'s `app.colors()` call and the analytics charts).

Routes still have no `/api` prefix — they're mounted directly at
`/users/{username}/...`, and every frontend call goes through
`api.client()`/`api.auth_headers()` consistently with that, so keep new
frontend calls consistent with it too rather than assuming a REST-style
`/api` namespace. No page carries a server-side auth guard: each reads
`app.storage.user` at render time (or, for pages with no page-load
fetch, inside its click handler) and reacts to the backend's actual
401/403 rather than gating the route itself. `src/frontend/` is a pure
HTTP client of the REST API in `app.py` — it must never import
`models`, `database`, `auth`, or `analytics` from `src/backend/app/`.

### Subagents and skills (`.claude/agents/`, `.claude/skills/`) — mandatory by default

**Every change to this repository goes through the agent pipeline
described in `AGENTS.md`** — plan → red → design → implementation →
verify (`pytest` from `src/backend/app/` per the cwd note above, `ruff
check`/`ruff format --check` from the repo root) → gate → close.
`AGENTS.md`'s table and diagram are the source of truth for which
subagent performs each stage and why — don't duplicate that mapping
here, so this section doesn't go stale every time an agent is added,
renamed, or reordered (it already had, once).

This is the default and is not optional by omission: do not implement
directly, skip the red step, or commit without the gate step's approval
just because a change looks small, purely visual, or urgent.
The only way to skip a step is the user explicitly authorizing that
specific piece of work to skip it, in that conversation — a general
instruction to move fast or "just do it" is not that authorization, and
one authorized bypass does not carry forward to later, unrelated
changes. When a step is skipped this way, say so plainly once the work
is reconciled into `.elm/ARCHITECTURE.md`/`.elm/TASKS.md` — the way the
2026-09-09 visual redesign's retroactive entries do it — never silently.

Supporting skills for these agents live in `.claude/skills/` (indexed in
`.claude/SKILLS.md`): `running-pytest-tests` (pytest invocations and how
to tell a real red state from a broken one), `checking-dependencies-with-
context7` (look up current dependency API shape — see "Dependency
changes" above), and `reviewing-atomic-commits` (read-only `git`/`gh`
inspection for the commit gate). None of `pytest`, `ruff`, `git`, or `gh`
is currently allow-listed anywhere in this repo, so expect a permission
prompt on each of these commands rather than assuming they run silently.

After every `qc-specialist` run, read `.claude/qc.log`'s newest entry
directly rather than relying only on its relayed summary — that log is
the one place its full Verdict/Tests/Lint/Format/Process-note report
lands, append-only, and terse relays have caused real back-and-forth on
this project before.

# Commit conventions

- Atomic commits: one logical change per commit, imperative-mood subject
  line, no mixed-concern commits.
- Never add a "Co-Authored-By" line, a "Generated with Claude Code" line,
  or any other Anthropic/Claude.ai attribution to a commit message, PR
  description, or other git metadata.
- This is a CLAUDE.md instruction, which is context rather than hard
  enforcement — for a guarantee, also clear `attribution` in
  `.claude/settings.json` as a belt-and-suspenders measure.