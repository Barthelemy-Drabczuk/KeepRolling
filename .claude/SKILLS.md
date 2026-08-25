# Skills

This project uses a few Claude Code skills to give the subagents in
`AGENTS.md` working knowledge of specific tools (pytest/ruff, `gh`)
without re-deriving it each time. Their actual definitions live
one-per-directory under `.claude/skills/`, since that's how skills are
loaded; this file is the human-readable overview that ties them to the
subagents that use them — it is not itself loaded as a skill.

| Skill | File | Used by | Purpose |
|---|---|---|---|
| `running-pytest-tests` | `.claude/skills/running-pytest-tests/SKILL.md` | `requirement-specialist`, `qc-specialist` | Correct `pytest` invocations for the red step and the full-suite verify step (including the `backend/app/` cwd requirement this project's bare imports need), and how to tell a valid red state from a broken one. |
| `reviewing-atomic-commits` | `.claude/skills/reviewing-atomic-commits/SKILL.md` | `commit-reviewer` | Read-only `gh` inspection commands and the atomicity/commit-message checks to run against a staged diff. Reference material only — does not cover running `git commit` or `gh pr create`. |
| `checking-dependencies-with-context7` | `.claude/skills/checking-dependencies-with-context7/SKILL.md` | main thread / whoever writes implementation code | Look up current dependency API shape via the `context7` MCP before writing code against it, per the rule in `CLAUDE.md`. |

## Why permissions still matter separately

A skill's content is documentation loaded into context — it does not by
itself suppress Claude Code's permission prompts for `Bash` commands.
None of the commands these skills document (`pytest`, `ruff check`, `ruff
format --check`, `git status`, `git diff`, `gh pr view`, `gh pr checks`,
`gh repo view`) is allow-listed anywhere in this repo yet, so every one of
them currently prompts each time it runs. An allow-list (in Claude Code's
permission settings) is the way to remove that friction, if it's ever set
up — nothing about the skills themselves changes when that happens.

## Adding a skill later

Follow the same shape: one directory with a `SKILL.md` under
`.claude/skills/`, YAML frontmatter with at minimum `name` and
`description` (third person, starts with "Use when...", no workflow
summary — see the description for why), and a row added to the table
above. See `AGENTS.md` for the subagents these skills serve and
`CLAUDE.md`/`BUSINESS.md` for the process/business rules behind them.
