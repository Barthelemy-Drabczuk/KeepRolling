# STACK.md

Maps path prefixes in this repository to the stack profile that governs
them — which "red," "verify," and "green" concretely mean for code under
that prefix. Read by `qc-specialist` and `commit-reviewer` (via the
`stack-profiles` skill) to pick the right format/lint/test commands, and
by `requirement-specialist`/`task-manager-specialist` to fill in a
requirement's `Stack:` field in `elm/REQUIREMENTS.md`.

| Path prefix | Stack |
|---|---|
| `backend/app/` | `python-pytest` |

Only one stack is defined today — this project has no infrastructure
code (no Terraform, no IaC of any kind) as of this writing. Add a new
stack the same way AGENTS.md describes for a seventh subagent: a row
here, plus a reference file under
`.claude/skills/stack-profiles/references/`.
