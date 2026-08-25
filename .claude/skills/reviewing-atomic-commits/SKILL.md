---
name: reviewing-atomic-commits
description: Use when reviewing a staged git diff before a commit lands — checking it's one logical change, checking the draft commit message against project convention, or checking gh CLI state (PR/checks/repo) as review context. Read-only: does not cover running git commit or gh pr create.
---

# Reviewing Atomic Commits

## Overview

This skill is for reviewing a change before it's committed, not for
committing it. `commit-reviewer` advises and blocks/approves; it never
runs `git commit` or `gh pr create` itself — that stays with the main
thread. Everything below is read-only inspection.

## When to Use

Before approving a commit: inspect exactly what's staged, judge whether
it's one logical change, check the draft message against convention, and
pull in `gh` context (open PR, CI checks) when it's relevant to the
review.

## Inspecting the Staged Diff

| Command | Purpose |
|---|---|
| `git status` | What's staged vs. unstaged vs. untracked |
| `git diff --staged` | The exact change about to be committed |
| `git diff --staged --stat` | Quick shape check — how many files, how spread out |
| `git log -1 --stat` | Compare against the prior commit's shape/size for context |

**Atomicity check:** if `git diff --staged --stat` touches unrelated
directories/crates, or the diff mixes a behavior change with unrelated
formatting/refactor noise, that's a mixed-concern commit — call it out and
suggest a split, don't approve as-is.

## Commit Message Convention

Cross-references CLAUDE.md's commit conventions — don't duplicate them
here, just check the draft message against:
- Imperative mood subject line, describes the one change accurately.
- No "Co-Authored-By" line, no "Generated with Claude Code" line, no other
  Anthropic/Claude.ai attribution anywhere in the message. Non-negotiable.

## Read-Only `gh` Context

Use these only to gather review context — never to open, merge, or modify
anything:

| Command | Purpose |
|---|---|
| `gh pr view` | Is this branch already tied to an open PR? What does it say? |
| `gh pr checks` | Is CI green on the current head, if a PR exists? |
| `gh repo view` | Confirm which repo/remote this is, when relevant |

If the repo has no remote configured yet (common in an early-stage POC),
these commands will error cleanly — that's expected, not something to fix
as part of a review.

## Common Mistakes

- Approving a commit that bundles an unrelated formatting pass with the
  actual logical change — split it instead.
- Treating a stale `qc-specialist` report as still valid — if there's any
  doubt, re-run the checks yourself rather than trusting a prior report.
- Reaching for `git commit` or `gh pr create` — not this skill's job; flag
  what needs to change and hand the decision back to the main thread.

Used by `commit-reviewer` — see root `SKILLS.md`.
