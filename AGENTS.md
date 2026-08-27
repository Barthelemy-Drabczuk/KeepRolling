# Agents

This project uses six Claude Code subagents to enforce the
requirement-to-commit flow required by `CLAUDE.md`. Their actual
definitions — the files Claude Code reads — live one-per-file under
`.claude/agents/`, since that's how subagents are actually loaded; this
file is the human-readable overview that ties them together and is not
itself read as a subagent definition.

## Repository layout

This project spans two git repositories. The code repo is this one;
`REQUIREMENTS.md`, `ARCHITECTURE.md`, and `TASKS.md` live in a separate
ledger repository, checked out here as a git submodule at `elm/`.

**Why a submodule and not a plain sibling clone:** a submodule pins one
exact commit of `elm/` inside the code repo's own commit history. That
pointer is what recovers the property a single repo gives you for
free — "what did the ledger say at the moment this code was committed"
— which a plain sibling clone, with no such pin, would simply lose.

**Current setup:** done. `elm/` points at a local bare repo,
`/home/percevase/Documents/Projets/moodometer-elm.git` — there's no
hosted remote for it yet. `elm/`'s own history starts with one seed
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
having hosted the ledger anywhere yet. Move `elm/` to a real remote
(anything reachable over `https://`/`ssh://`) and re-point `.gitmodules`
the same way you'd repoint any submodule, and this restriction goes away
because the default-denied transport is `file`, not `http`/`ssh`.

**Setting up a *new* ledger from scratch** (documented for completeness —
not needed again on this repo), from the code repo root:
```
mkdir elm && git -C elm init
git -C elm commit --allow-empty -m "chore: initialize elm ledger repo"
# push elm/ to its own remote if you want it shared, then:
git submodule add <elm-remote-url> elm
git add .gitmodules elm && git commit -m "chore: add elm ledger as submodule"
```

**The convention every agent and the main thread follow:**
- Reads and writes to the ledger go through the `elm/` path
  (`elm/REQUIREMENTS.md`, etc.) — the writer agents already do this.
- Every commit-reviewer pass reviews exactly one repository's staged
  diff: `git -C elm diff --staged` for a ledger change, plain `git
  diff --staged` from the code repo root for a code change. Never let
  one commit span both.
- After a commit lands inside `elm/`, the code repo needs a small
  follow-up commit bumping its submodule pointer forward (`git add elm
  && git commit -m "chore: bump elm ref"`) — otherwise the code repo's
  history keeps citing a stale ledger state. commit-reviewer approves
  these on sight; the diff is always exactly one pinned commit.
- Never force-push or rewrite history on either repository past a
  commit the other one already references — that reference has no
  fallback the way a same-repo commit hash would.

Expect roughly one extra "bump elm ref" commit per ledger change —
that's the real, ongoing cost of the split. It buys independent
governance and lifecycle for requirements/design/tasks versus code.

| Subagent | File | Role in the loop | Can write code? |
|---|---|---|---|
| `task-manager-specialist` | `.claude/agents/task-manager-specialist.md` | **Plan / Close.** Breaks an epic into an ordered backlog of atomic requirements before work starts, and closes each one out — commit hash and traceability recorded — after it lands. | No — backlog file only |
| `requirement-specialist` | `.claude/agents/requirement-specialist.md` | **Red.** Reads a requirement, checks it against the INCOSE bar in `CLAUDE.md`, records the outcome in `elm/REQUIREMENTS.md` (via the `requirements-traceability` skill), and writes a failing test for it. Refuses to guess at ambiguous requirements — reports back instead. | Tests + the requirements ledger, never implementation |
| `design-specialist` | `.claude/agents/design-specialist.md` | **Design.** Fits the requirement into the existing architecture, defines the interface/contract implementation must satisfy (checking `design-patterns`, `ux-patterns`, or `ui-patterns` first, depending on whether the component is backend, interaction, or visual), flags drift before code is written. | No — architecture doc only |
| `qc-specialist` | `.claude/agents/qc-specialist.md` | **Verify.** Runs the applicable stack's format, lint, and test commands (see `stack-profiles`), logs its own run to `.claude/qc.log`, and reports a pass/fail summary to the main thread. | No — read/run only |
| `commit-reviewer` | `.claude/agents/commit-reviewer.md` | **Gate.** Reviews the staged diff before any commit: atomicity, commit-message conventions, clean verify state, blast radius on infra diffs. Approves or blocks. | No — read/run only |
| `schedule-tracker` | `.claude/agents/schedule-tracker.md` | **Health (cross-cutting).** Reads `elm/TASKS.md` at any time and reports stale items, current velocity, and schedule risk against any stated milestone. Not a step in any single item's flow. | No — read-only, no file of its own |

## Stack profiles

None of the six agents hardcode a language or toolchain — `STACK.md`
at the repo root maps path prefixes to stacks, and the `stack-profiles`
skill defines what "red," "verify," and "green" concretely mean for
each one (currently Python and Terraform, though this repo has no
Terraform code yet — the `infra/` row is there for whenever it does;
add a stack by adding a row to `STACK.md` and a reference file to the
skill).

This is also the mechanism behind building "the code and what it runs
on" together: a requirement carries a `Stack:` field in
`elm/REQUIREMENTS.md`, and when it needs both infrastructure and code,
`task-manager-specialist` splits it into two atomic backlog items —
infrastructure first, since code referencing a resource can't go green
before that resource exists. Each half goes through the full loop
independently, against its own stack's profile; `design-specialist`'s
contract for the requirement is what keeps the two halves consistent
with each other without either one needing to know the other's
toolchain.

## Pattern toolboxes

`design-specialist` draws from three parallel toolboxes when defining
a contract, built to the same shape as `stack-profiles`: a compact
symptom table in `SKILL.md`, one reference file per pattern loaded
only when it's actually selected, so the cost of a toolbox existing is
nearly zero until a requirement actually needs it. `design-patterns`
covers software component shape (Strategy, Factory, Builder, ...);
`ux-patterns` covers interaction and flow (Wizard/Stepper, Progressive
Disclosure, ...); `ui-patterns` covers visual layout and presentation
(Card, Modal, Design Tokens, ...). A single requirement can draw from
more than one — see any toolbox's own note on combining with the
others. Add a fourth the same way if a new kind of contract recurs
enough to be worth naming (a `STACK.md` entry for whatever stack
builds it would usually follow close behind).

## How they fit together

```
requirement / epic
        │
        ▼
task-manager-specialist  ───────────────────────────────────────┐  (plan)
        │  ordered, atomic backlog item                         │
        ▼                                                        │
requirement-specialist  →  failing test                 (red)   │
        │                                                        │
        ▼                                                        │
design-specialist  →  interface contract, drift check  (design) │
        │                                                        │
        ▼                                                        │
implementation written                                    (green)│
        │                                                        │
        ▼                                                        │
qc-specialist  →  pass/fail, lint, format summary       (verify)│
        │                                                        │
        ▼                                                        │
commit-reviewer  →  approve / block                       (gate)│
        │                                                        │
        ▼                                                        │
git commit  ─────────────────────────────────────────────────────┘
        │
        ▼
task-manager-specialist  (close: commit hash + traceability,
                           surfaces next unblocked item)
```

`schedule-tracker` isn't a step in the diagram above — it reads the
same `elm/TASKS.md` that `task-manager-specialist` writes to, at any point
in a session, and reports on the backlog as a whole rather than on any
single item's progress. Call it at the start of a session or whenever
you want a health check; it never blocks or reorders the flow above.

Only `requirement-specialist`, `design-specialist`, and the main thread
ever write test, design, or source content — and each is scoped to one
lane (tests only, architecture doc only, source respectively).
`task-manager-specialist`, `qc-specialist`, `commit-reviewer`, and
`schedule-tracker` are deliberately read/run-only against code and
tests — their job is to observe, sequence, and report, not to fix — so
a problem they find always comes back to the main thread as a
decision, not a silent correction.

## The golden thread

Every atomic unit of work should be traceable end to end: requirement
ID → design element (if any) → test file → commit hash, recorded in
`elm/TASKS.md` by `task-manager-specialist` alongside a timestamp on every
status change. If you can't answer "which commit satisfied requirement
R-014" by reading `elm/TASKS.md`, the thread has broken somewhere and it's
worth finding out where before adding more work on top of it. That same
timestamp is what makes `schedule-tracker`'s staleness and velocity
reporting possible — it has nothing to compute from if the timestamp
goes stale.

## The requirements ledger

`elm/REQUIREMENTS.md` is the system of record for a requirement's own
content — its exact accepted wording, its INCOSE result, and whether
it's since been superseded. It is not the same thing as `elm/TASKS.md`:
`elm/TASKS.md` tracks a backlog item's *state* (todo → done) and the
commit hash; `elm/REQUIREMENTS.md` tracks the requirement's *content* and
history, append-only, version-controlled the same way code is. Both
reference the same requirement ID rather than duplicating each other.
See the `requirements-traceability` skill for the entry schema and the
commit convention that keeps its git history trustworthy.

## Adding a seventh subagent later

Follow the same shape: one Markdown file per agent under
`.claude/agents/`, YAML frontmatter with at minimum `name` and
`description`, restrict `tools` to the minimum the role needs, and add
a row to the table above. See `CLAUDE.md` for the process rules these
agents are enforcing, and `BUSINESS.md` for why those rules exist.

**Choosing a model tier:** the question isn't how important the agent
sounds, it's whether anything else in the loop independently re-checks
the same failure mode. Use `opus` where the agent is the sole
checkpoint for its class of error (`requirement-specialist`'s INCOSE
judgment, `design-specialist`'s architectural fit — nothing downstream
re-derives either). Use `sonnet` where there's real judgment but either
partial redundancy elsewhere or the judgment is over one bounded,
already-concrete artifact rather than open-ended interpretation
(`task-manager-specialist`'s decomposition, `commit-reviewer`'s diff
review). Use `haiku` where the work is mechanical or a downstream step
independently re-verifies the same thing anyway (`qc-specialist`,
fully re-checked by `commit-reviewer`; `schedule-tracker`, read-only
and advisory with nothing acting on it automatically).

**Giving an agent access to a skill:** a `tools:` allowlist that omits
`Skill` — every agent above has one — means that agent cannot discover
or invoke skills at runtime, regardless of what its own instructions
say. Preload the specific skill(s) it needs instead, with a `skills:`
frontmatter field naming each by its directory name (e.g.
`requirements-traceability`, `stack-profiles`). This is deterministic
— the content is present from the start — rather than relying on the
agent choosing to look something up.

## Stakeholder agents

`.claude/agents/stakeholders/` holds an open-ended, user-extensible set
of upstream agents that feed `BUSINESS.md` — stakeholder needs, market
context, prior art — rather than participating in the red-design-green-
verify-gate loop. Claude Code scans agent subfolders recursively, so
this works the same as the flat pipeline agents; only `name` has to
stay unique across the whole `.claude/agents/` tree. (If the
`stakeholders/` folder is brand new, restart the session once so Claude
Code picks it up — it only watches directories that existed when the
session started.)

Two examples ship here: `research-specialist` (prior art, published
research, technical precedent) and `business-specialist` (market
context, competitive positioning). Add more the same way — a
`WebSearch`/`WebFetch`-capable agent that appends findings, cited, to
its own dated section of `BUSINESS.md`, never edits another
contributor's section, and never touches `elm/`, any pipeline agent's
files, or implementation. `requirement-specialist` reads `BUSINESS.md`
for context but is the only agent that decides whether something there
is well-formed enough to become a requirement — a stakeholder agent
that finds a genuine gap surfaces it in `BUSINESS.md`'s "Open
questions" section rather than drafting the requirement itself.
