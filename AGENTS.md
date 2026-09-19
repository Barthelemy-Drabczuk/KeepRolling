# Agents

This project enforces its requirement-to-commit flow with the five
Claude Code subagents shipped by the **`req-to-commit-pipeline`** plugin
(`braindot` marketplace), not the bespoke one-per-file agents this repo
used to define locally. Those local files still exist under
`.claude/agents/` but are **retired** — no longer part of the active
loop — kept on disk only as historical reference for how this project's
process evolved (see "Migration note" below). The plugin's own agent
definitions live in its installed package, not in this repo; invoke them
by their namespaced name, e.g. `req-to-commit-pipeline:requirement-specialist`.

## Repository layout

This project spans two git repositories. The code repo is this one;
`REQUIREMENTS.md`, `ARCHITECTURE.md`, and `TASKS.md` — "the ledger" in
the plugin's own terminology — live in a separate ledger repository,
checked out here as a git submodule at `.elm/`. This is the plugin's
`ledger-layout` skill's "submodule layout (advanced, opt-in)" option;
this note is the explicit, named anchor that skill's detection rule
looks for, so don't remove it without updating that skill's expectation
too.

**Why a submodule and not a plain sibling clone:** a submodule pins one
exact commit of `.elm/` inside the code repo's own commit history. That
pointer is what recovers the property a single repo gives you for
free — "what did the ledger say at the moment this code was committed"
— which a plain sibling clone, with no such pin, would simply lose.

**Current setup:** done. `.elm/` points at a local bare repo,
`/home/percevase/Documents/Projets/moodometer-elm.git` — there's no
hosted remote for it yet. `.elm/`'s own history starts with one seed
commit carrying the pre-split `TASKS.md`/`ARCHITECTURE.md` content
(moved here verbatim from this repo's former root-level copies) plus a
fresh `REQUIREMENTS.md`.

**Known consequence of a local-only origin:** git disables the `file://`
submodule transport by default as a security guard (CVE-2022-39253), so
`git submodule update --init` — needed by any *fresh* clone of this code
repo, including this one before its first use — fails with `transport
'file' non permis` unless that clone's git config explicitly allows it
for this one operation:
```
git -c protocol.file.allow=always submodule update --init
```
This isn't a workaround to "fix" later — it's the honest cost of not
having hosted the ledger anywhere yet. Move `.elm/` to a real remote
(anything reachable over `https://`/`ssh://`) and re-point `.gitmodules`
the same way you'd repoint any submodule, and this restriction goes away
because the default-denied transport is `file`, not `http`/`ssh`.

**The convention every agent and the main thread follow:**
- Reads and writes to the ledger go through the `.elm/` path
  (`.elm/REQUIREMENTS.md`, etc.) — the writer agents already do this.
- Every Gate-mode pass (`qc-gate-specialist`) reviews exactly one
  repository's staged diff: `git -C .elm diff --staged` for a ledger
  change, plain `git diff --staged` from the code repo root for a code
  change. Never let one commit span both.
- After a commit lands inside `.elm/`, the code repo needs a small
  follow-up commit bumping its submodule pointer forward (`git add .elm
  && git commit -m "chore: bump .elm ref"`) — `project-manager`'s
  commit-and-close step (Mode B) handles this the same way
  `task-manager-specialist` used to; the diff is always exactly one
  pinned commit and needs no further review.
- Never force-push or rewrite history on either repository past a
  commit the other one already references — that reference has no
  fallback the way a same-repo commit hash would.

Expect roughly one extra "bump .elm ref" commit per ledger change —
that's the real, ongoing cost of the split. It buys independent
governance and lifecycle for requirements/design/tasks versus code.

| Subagent | Role in the loop | Can write code? |
|---|---|---|
| `req-to-commit-pipeline:requirement-specialist` | **Red.** Reads a requirement, checks it against the INCOSE bar in `CLAUDE.md`, records the outcome in `.elm/REQUIREMENTS.md` (via the `requirements-traceability` skill), and writes a failing test for it. Refuses to guess at ambiguous requirements — reports back instead. | Tests + the requirements ledger, never implementation |
| `req-to-commit-pipeline:frontend-designer` | **Visual exploration** (UI-facing requirements only, ahead of design). Sends a brief to a shared Lovable mockup project, gets back a live preview, and translates it into a written ux-patterns/ui-patterns contract for `solution-specialist`. Lovable's own generated code is never merged. Optional — skip entirely for backend-only requirements. | No — reports a contract + preview link only |
| `req-to-commit-pipeline:solution-specialist` | **Design mode:** fits the requirement into the existing architecture, defines the interface/contract implementation must satisfy (checking `design-patterns`, `ux-patterns`, or `ui-patterns` first), flags drift before code is written. **Stakeholder-research mode** (any time, outside the loop): market/competitive grounding or prior-art/technical precedent, feeding `BUSINESS.md` — this absorbs what the old `business-specialist`/`research-specialist` stakeholder agents did separately. | Design mode: `.elm/ARCHITECTURE.md` only. Research mode: `BUSINESS.md` only. |
| `req-to-commit-pipeline:qc-gate-specialist` | **Verify mode** (after implementation): runs the applicable stack's format, lint, and test commands (see `stack-profiles`), logs its run to `.claude/qc.log` — same file and format the old `qc-specialist` used, still read its newest entry directly rather than trusting only the relayed summary. **Gate mode** (before commit): reviews the staged diff for atomicity, commit-message conventions, a re-confirmed clean verify state, and blast radius; approves or blocks. | No — read/run only, both modes |
| `req-to-commit-pipeline:project-manager` | **Mode A (plan):** breaks an epic into an ordered, WIP-limited backlog of atomic requirements. **Mode B (commit + close):** once Gate mode approves, *writes and runs the commit itself* (plus any requested GitHub follow-up), then closes the task out — commit hash and traceability in `.elm/TASKS.md`. **Mode C (health):** reports `.elm/TASKS.md` as a Kanban board — bottlenecks, staleness, cycle time, schedule risk. | Mode A/B: backlog file + git/GitHub operations, never test/design/source content. Mode C: read-only. |

**Real change from the old pipeline, worth knowing:** `project-manager`'s
Mode B actually runs `git commit` (and, if asked, push/PR/issue
operations) once Gate mode approves — the old `task-manager-specialist`
never touched git itself; the main thread committed after
`commit-reviewer`'s approval. Point `project-manager` at exactly what
git/GitHub follow-up you want per requirement if you don't want it
pushing or opening a PR on its own.

## Stack profiles

None of the five agents hardcode a language or toolchain — `STACK.md`
at the repo root maps path prefixes to stacks, and the `stack-profiles`
skill defines what "red," "verify," and "green" concretely mean for
each one (Python and Terraform ship as the plugin's starting profiles,
though this repo has no Terraform code yet — the `infra/` row is there
for whenever it does).

**Rewiring the plugin for a fourth stack it doesn't ship, `python-frontend`:**
this project has a third `STACK.md` row, `python-frontend`, for
`src/frontend/` — a NiceGUI page's "red"/"verify" means something
narrower than a plain backend module (most interaction is
manual-verification-only; only pure functions and server-rendered
initial state get real automated red/green). The plugin's own
`stack-profiles` skill (`req-to-commit-pipeline:stack-profiles`,
deterministically preloaded by `requirement-specialist` and
`qc-gate-specialist` via their `skills:` frontmatter) ships only the
generic Python and Terraform profiles and has no way to see a
project-local addition to it — a plugin agent's preloaded skill resolves
to the plugin's own bundled copy, never this repo's `.claude/skills/`.
Rather than relying on remembering to attach it per invocation, the
profile is inlined below so it travels with this file, which every
agent already reads as project context:

> **Python / NiceGUI frontend profile (`python-frontend`, `src/frontend/`)**
>
> Same language and test runner as the plain `python` profile, but
> narrower: most of what a page *does* at runtime is not observable
> through `pytest` at all, and one specific NiceGUI testing mechanism is
> banned outright.
>
> - **Location:** despite living outside `src/backend/`, frontend tests
>   live with the backend's, under `src/backend/app/tests/` (no separate
>   frontend test directory) — `src/backend/app/pytest.ini`'s
>   `pythonpath` entry is what makes `from frontend.history import ...`
>   resolve from there. Page-shape assertions mostly live in
>   `test_frontend.py`; a page with its own pure helpers gets its own
>   `test_<page>.py`/`test_<page>_page.py`, matching sibling pages
>   (`test_history.py`, `test_analytics_page.py` — the `_page` suffix
>   avoids colliding with a same-named backend test module).
> - **Red confirmation:** run `pytest` from `src/backend/app/`, same as
>   the `python` profile. Frontend-specific trap: a `client.get(...)`
>   against a route that crashes only on an *authenticated* branch won't
>   fail the way you'd expect — `app.storage.user` cannot be seeded over
>   HTTP, so that branch is outside what a `pytest` red state can express
>   at all.
> - **Verify commands:** identical to `python` — `ruff format --check .`
>   / `ruff check .` from the repo root, `pytest` from `src/backend/app/`,
>   full suite.
> - **`nicegui.testing.user`/`nicegui.testing.Screen` are banned
>   outright** — they reset NiceGUI's process-global `ui.run`/`ui.run_with`
>   state on teardown, corrupting the shared `client` fixture for every
>   test alphabetically after the one that used them (observed: 82
>   errors across the suite). Use the plain `client`/`TestClient` fixture
>   instead — it proves more than it looks like it does: initial
>   server-rendered content (a label's text, a button's caption/colour
>   prop, a link's `href`, anything rendered from an initial pre-interaction
>   read) is genuinely assertable via `client.get(path).text`.
> - **Live client-side interaction is manual-verification-only** —
>   pointer drags, real key events, anything needing a websocket
>   round-trip. Split a page's contract three ways: pure logic (a plain
>   unit test), initial render (the `client` fixture), live interaction
>   (manual, via `cd src/backend/app && uvicorn app:app --reload`,
>   recorded in the commit message).
> - **Push an assertion down to the REST layer** instead of observing it
>   through the UI, whenever the same behavior already has a
>   `python`-profile test — re-asserting the same response shape through
>   rendered HTML is redundant and more fragile.
> - **`app.storage.user` cannot be seeded over HTTP** — any branch
>   depending on a logged-in session is manual-verification-only for the
>   same reason as live interaction.
>
> (Full version, in case this copy ever drifts:
> `.claude/skills/stack-profiles/references/python-frontend.md`.)

This stack-per-path split is also the mechanism behind building "the
code and what it runs on" together: a requirement carries a `Stack:`
field in `.elm/REQUIREMENTS.md`, and when it needs both infrastructure
and code, `project-manager`'s Mode A splits it into two atomic backlog
items — infrastructure first, since code referencing a resource can't go
green before that resource exists. `solution-specialist`'s Design-mode
contract keeps the two halves consistent without either needing to know
the other's toolchain.

## Pattern toolboxes

`solution-specialist`'s Design mode draws from three parallel toolboxes
when defining a contract, built to the same shape as `stack-profiles`: a
compact symptom table in `SKILL.md`, one reference file per pattern
loaded only when it's actually selected. `design-patterns` covers
software component shape (Strategy, Factory, Builder, ...);
`ux-patterns` covers interaction and flow (Wizard/Stepper, Progressive
Disclosure, ...); `ui-patterns` covers visual layout and presentation
(Card, Modal, Design Tokens, ...). A single requirement can draw from
more than one — see any toolbox's own note on combining with the
others.

## Flow control: small units, low WIP

The plugin's `project-manager` Mode A enforces a WIP limit per
in-progress column, read from a header at the top of `.elm/TASKS.md`
(`todo` / `red` / `design` / `green` / `verify` / `gate` / `done` /
`blocked`), and `requirement-specialist` fast-checks a word limit on
requirement text (100 words by default) before the full INCOSE pass.

**Rewiring for this project: preset limits, don't bootstrap your own.**
`.elm/TASKS.md` predates this plugin feature and has no WIP-limits
header yet. `project-manager`'s own instructions have it invent modest
defaults the first time it writes a header — instead, the next time
`project-manager` touches `.elm/TASKS.md` (Mode A or Mode C), it should
write exactly these numbers rather than picking its own, since nothing
in this project's history yet tells it where the real bottlenecks are:

```
red: 2
design: 2
gate: 2
green: 3
verify: 3
```

Mode C's own reporting is what should change these later — raise or
lower a number once it actually reports a column running over, not
before.

## How they fit together

```
requirement / epic
        │
        ▼
project-manager Mode A  ────────────────────────────────────────┐  (plan)
        │  ordered, atomic backlog item                         │
        ▼                                                        │
requirement-specialist  →  failing test                 (red)   │
        │                                                        │
        ▼                                                        │
frontend-designer  →  mockup + UI/UX contract  (UI-facing only) │
        │       (skipped entirely for backend-only requirements)│
        ▼                                                        │
solution-specialist Design mode  →  contract, drift check(design)│
        │                                                        │
        ▼                                                        │
implementation written                                    (green)│
        │                                                        │
        ▼                                                        │
qc-gate-specialist Verify mode  →  pass/fail summary     (verify)│
        │                                                        │
        ▼                                                        │
qc-gate-specialist Gate mode  →  approve / block           (gate)│
        │                                                        │
        ▼                                                        │
project-manager Mode B  →  commit + optional push/PR,     ──────┘
                            then close (hash + traceability
                            in .elm/TASKS.md, surfaces next
                            unblocked item)
```

`solution-specialist`'s Stakeholder-research mode and `project-manager`'s
Mode C aren't steps in the diagram above — either can run at any point
in a session, independent of any single item's progress. Call either
whenever useful; neither blocks or reorders the flow above.

Only `requirement-specialist`, `solution-specialist`'s Design mode, and
the main thread ever write test, design, or source content — each
scoped to one lane. `project-manager`'s Mode A, `frontend-designer`, and
`qc-gate-specialist` (both modes) are deliberately read/run-only against
this repo's code and tests. `project-manager`'s Mode B is the one
exception: it writes git/GitHub state that Gate mode has already
approved, never content of its own judgment.

## The golden thread

Every atomic unit of work should be traceable end to end: requirement ID
→ design element (if any) → test file → commit hash, recorded in
`.elm/TASKS.md` by `project-manager` alongside a timestamp on every
status change. If you can't answer "which commit satisfied requirement
R-014" by reading `.elm/TASKS.md`, the thread has broken somewhere and
it's worth finding out where before adding more work on top of it. That
same timestamp is what makes Mode C's staleness and flow reporting
possible.

## The requirements ledger

`.elm/REQUIREMENTS.md` is the system of record for a requirement's own
content — its exact accepted wording, its INCOSE result, and whether
it's since been superseded. It is not the same thing as `.elm/TASKS.md`:
`.elm/TASKS.md` tracks a backlog item's *state* (todo → done) and the
commit hash; `.elm/REQUIREMENTS.md` tracks the requirement's *content*
and history, append-only, version-controlled the same way code is. Both
reference the same requirement ID rather than duplicating each other.
See the `requirements-traceability` skill for the entry schema and the
commit convention that keeps its git history trustworthy.

## Stakeholder research

`solution-specialist`'s Stakeholder-research mode covers what this
repo's two retired local agents did separately
(`business-specialist` for market/competitive grounding,
`research-specialist` for prior-art/technical precedent) — both fed
`BUSINESS.md` the same way and neither touched the ledger, so they
merged into one mode covering both flavors of research. Whichever angle
is invoked, `requirement-specialist` reads `BUSINESS.md` for context but
is the only agent that decides whether something there is well-formed
enough to become a requirement — a research finding that surfaces a
genuine gap goes into `BUSINESS.md`'s "Open Questions" section rather
than being drafted into a requirement directly.

## Optional external skills

`solution-specialist` (Design mode) and `qc-gate-specialist` (Gate mode)
both check at runtime whether `universal-coding-standards` is available
and invoke it if so — it ships with the separate `universal-programming`
plugin (same `braindot` marketplace), which **is already installed** in
this environment, so both modes get its extra code-quality checks
automatically. This is a different mechanism from every other skill
reference here: it's a runtime "if available" check, not a deterministic
`skills:` frontmatter preload, so its absence would never block the
pipeline — it just happens to already be present.

## Migration note: the old local pipeline

Before this plugin, this project ran its own seven-plus-stakeholder
subagent set under `.claude/agents/` (`task-manager-specialist`,
`requirement-specialist`, `frontend-designer`, `design-specialist`,
`qc-specialist`, `commit-reviewer`, `schedule-tracker`, plus
`stakeholders/business-specialist.md` and
`stakeholders/research-specialist.md`). Those files are untouched on
disk but are no longer part of the active loop — every responsibility
they covered now lives in one of the five plugin agents above (see the
table's role descriptions for the mapping). They have not been deleted;
removing them is a separate decision the project owner can make once
comfortable the plugin covers everything they did.

## Adding another subagent later

The plugin's five agents cover the core loop; a genuinely new,
project-specific responsibility that doesn't belong in any of their
existing modes still follows the old local shape: one Markdown file
under `.claude/agents/`, YAML frontmatter with at minimum `name` and
`description`, `tools` restricted to the minimum the role needs, and a
`skills:` field naming any skill it should preload deterministically.
Prefer this only for something genuinely local to this repo — anything
that would make sense in any project using this plugin belongs upstream
as a new mode on an existing plugin agent instead (see the plugin's own
`AGENTS.md` for that shape), not duplicated here.
