---
name: stack-profiles
description: Defines what "red" (failing test confirmation), "verify" (format/lint/test), and "green" concretely mean for each stack this project uses, keyed off STACK.md's path-prefix mapping. Use whenever requirement-specialist needs a red-confirmation command, qc-specialist or commit-reviewer needs format/lint/test commands, or task-manager-specialist needs to decide whether a requirement needs an infrastructure half before its code half. Load exactly one reference file for the stack that matches the changed path(s), not all of them.
---

# Stack profiles

A shortcut for routing to the right concrete commands instead of
re-deriving them from `pyproject.toml`/tooling config every time. The
project can span more than one stack (application code, infrastructure)
without any of the six pipeline agents hardcoding a language or
toolchain — they all go through this skill and `STACK.md` instead.

## Finding the right profile

1. Look up the changed path(s) against `STACK.md`'s prefix table at the
   repo root.
2. Load `references/<stack>.md` for that one stack. If a diff spans more
   than one stack's paths, load each stack's reference separately and
   run/report them as separate sections — never merge their output into
   one verdict (this mirrors `qc-specialist`'s and `commit-reviewer`'s
   own instructions).

## What every reference file defines

Each `references/<stack>.md` answers the same four questions, so any
agent using this skill can find the same information in the same shape
regardless of stack:

- **Red-confirmation** — the exact command to run a newly-added failing
  test (or its stack equivalent, e.g. a Terraform plan/test) and how to
  tell a *valid* red state (fails for the behavior under test) from an
  *invalid* one (fails on a typo, syntax error, or collection error).
- **Verify** — the exact format-check, lint, and full-test-suite
  commands, and the working directory each must run from.
- **Green** — what "the implementation satisfies the test" means
  concretely for this stack (usually: the same red-confirmation command
  now passes, plus the full suite still passes).
- **Infra-vs-code split signal** — for `task-manager-specialist`: what
  marks a requirement as needing this stack's half of a two-stack split
  (e.g., "references a resource/table/queue that doesn't exist yet").

## Currently defined

`references/python-pytest.md` — this project's only stack today (see
`STACK.md`). Add a new one the same way: a reference file answering the
four questions above, plus a row in `STACK.md`.
