# Agents

This project uses three Claude Code subagents to enforce the TDD flow
required by `CLAUDE.md`. Their actual definitions — the files Claude Code
reads — live one-per-file under `.claude/agents/`, since that's how
subagents are actually loaded; this file is the human-readable overview
that ties them together and is not itself read as a subagent definition.

| Subagent | File | Role in the TDD loop | Can write code? |
|---|---|---|---|
| `requirement-specialist` | `.claude/agents/requirement-specialist.md` | **Red.** Reads a requirement, checks it against the INCOSE bar in `CLAUDE.md`, and writes a failing test for it. Refuses to guess at ambiguous requirements — reports back instead. | Tests only, never implementation |
| `qc-specialist` | `.claude/agents/qc-specialist.md` | **Verify.** Runs the full suite, clippy, and fmt after implementation is written, and reports a pass/fail summary to the main thread. | No — read/run only |
| `commit-reviewer` | `.claude/agents/commit-reviewer.md` | **Gate.** Reviews the staged diff before any commit: atomicity, commit-message conventions, clean test/lint state. Approves or blocks. | No — read/run only |

## How they fit together

```
requirement  →  requirement-specialist  →  failing test   (red)
                                              │
                                              ▼
                                    implementation written   (green)
                                              │
                                              ▼
                                       qc-specialist          (verify)
                                              │
                                              ▼
                                      commit-reviewer         (gate)
                                              │
                                              ▼
                                         git commit
```

Only `requirement-specialist` and the main thread ever write source or
test code. `qc-specialist` and `commit-reviewer` are deliberately
read/run-only — their job is to observe and report, not to fix — so a
problem they find always comes back to the main thread as a decision,
not a silent correction.

## Adding a fourth subagent later

Follow the same shape: one Markdown file per agent under
`.claude/agents/`, YAML frontmatter with at minimum `name` and
`description`, restrict `tools` to the minimum the role needs, and add a
row to the table above. See `CLAUDE.md` for the process rules these
agents are enforcing, and `BUSINESS.md` for why those rules exist.
