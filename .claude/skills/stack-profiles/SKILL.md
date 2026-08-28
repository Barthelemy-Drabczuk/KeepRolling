---
name: stack-profiles
description: Defines what "red", "green", and "verify" concretely mean for each technology stack this project uses — Python/pytest, Terraform, or others. Use this whenever requirement-specialist needs to write or confirm a failing check, whenever qc-specialist or commit-reviewer needs to run verification, or whenever a requirement or diff spans more than one stack and the split needs to be understood. Trigger this before running any test/lint/format command — never assume pytest or ruff exist just because they did last time. Check STACK.md at the repo root, or the requirement's own Stack: field in .elm/REQUIREMENTS.md, before doing anything stack-specific.
---

# Stack profiles

Every requirement targets one or more technology stacks. This skill is
what keeps requirement-specialist, qc-specialist, and commit-reviewer
from hardcoding one language's tools into their own instructions.

## Determining the stack

1. Check `STACK.md` at the repo root — it maps path prefixes to
   stacks.
2. If you already know the requirement's ID, `.elm/REQUIREMENTS.md`'s
   `Stack:` field on that entry is authoritative — trust it over
   guessing from paths.
3. If a diff or requirement touches more than one stack's paths, treat
   it as multi-stack: apply each relevant profile separately. Never
   blend their commands or their pass/fail verdicts into one verdict.

Currently defined profiles:
- `references/python.md`
- `references/python-frontend.md`
- `references/terraform.md`

Add a new one the same way: one reference file per stack, covering the
same things every profile needs (below), plus a row in `STACK.md`.

## What every profile defines

- **Location & naming** — where source and tests/checks live, and how
  they're named.
- **Red confirmation** — the command(s) that prove a requirement isn't
  satisfied yet, and what "fails for the expected reason" means here.
  Every stack shares one rule regardless of its tooling: a test that
  fails on a typo, a syntax error, or a collection error you introduced
  is not a valid red state.
- **Verify commands** — format check, lint, full test run, in order.
- **Stack-specific cautions** — anything a reviewer coming from another
  stack would get wrong by assuming it works like code.

## Multi-stack requirements

"The code and what it runs on" often means one requirement's design
actually needs two atomic implementation units — one per stack — with
the infrastructure one typically ordered first, since code that
references a resource can't go green before that resource exists to
reference. That split is task-manager-specialist's job at decomposition
time. requirement-specialist and qc-specialist shouldn't try to paper
over a multi-stack unit by running every stack's commands as if they
were one.
