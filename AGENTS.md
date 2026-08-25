# Agents

This project uses six Claude Code subagents to enforce the
requirement-to-commit flow required by `CLAUDE.md`. Their actual
definitions — the files Claude Code reads — live one-per-file under
`.claude/agents/`, since that's how subagents are actually loaded; this
file is the human-readable overview that ties them together and is not
itself read as a subagent definition.

| Subagent | File | Role in the loop | Can write code? |
|---|---|---|---|
| `task-manager-specialist` | `.claude/agents/task-manager-specialist.md` | **Plan / Close.** Breaks an epic into an ordered backlog of atomic requirements before work starts, and closes each one out — commit hash and traceability recorded — after it lands. | No — backlog file only |
| `requirement-specialist` | `.claude/agents/requirement-specialist.md` | **Red.** Reads a requirement, checks it against the INCOSE bar in `CLAUDE.md`, and writes a failing test for it. Refuses to guess at ambiguous requirements — reports back instead. | Tests only, never implementation |
| `design-specialist` | `.claude/agents/design-specialist.md` | **Design.** Fits the requirement into the existing architecture, defines the interface/contract implementation must satisfy, flags drift before code is written. | No — architecture doc only |
| `qc-specialist` | `.claude/agents/qc-specialist.md` | **Verify.** Runs the full suite, ruff check, and ruff format after implementation is written, and reports a pass/fail summary to the main thread. | No — read/run only |
| `commit-reviewer` | `.claude/agents/commit-reviewer.md` | **Gate.** Reviews the staged diff before any commit: atomicity, commit-message conventions, clean test/lint state. Approves or blocks. | No — read/run only |
| `schedule-tracker` | `.claude/agents/schedule-tracker.md` | **Health (cross-cutting).** Reads `TASKS.md` at any time and reports stale items, current velocity, and schedule risk against any stated milestone. Not a step in any single item's flow. | No — read-only, no file of its own |

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
same `TASKS.md` that `task-manager-specialist` writes to, at any point
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
`TASKS.md` by `task-manager-specialist` alongside a timestamp on every
status change. If you can't answer "which commit satisfied requirement
R-014" by reading `TASKS.md`, the thread has broken somewhere and it's
worth finding out where before adding more work on top of it. That same
timestamp is what makes `schedule-tracker`'s staleness and velocity
reporting possible — it has nothing to compute from if the timestamp
goes stale.

## Adding a seventh subagent later

Follow the same shape: one Markdown file per agent under
`.claude/agents/`, YAML frontmatter with at minimum `name` and
`description`, restrict `tools` to the minimum the role needs, and add
a row to the table above. See `CLAUDE.md` for the process rules these
agents are enforcing, and `BUSINESS.md` for why those rules exist.
