---
name: requirements-traceability
description: Defines the entry schema for elm/REQUIREMENTS.md and the commit convention that keeps its history trustworthy. Use whenever requirement-specialist records a requirement's INCOSE result (accepted or rejected), or amends/supersedes a previously-accepted requirement. Not for elm/TASKS.md (status/sequencing — see task-manager-specialist) or elm/ARCHITECTURE.md (design contracts — see design-specialist).
---

# Requirements traceability

`elm/REQUIREMENTS.md` is the system of record for a requirement's own
*content* — its exact accepted (or rejected) wording, its INCOSE result,
and whether it's since been superseded. See AGENTS.md's "The
requirements ledger" section for how this differs from `elm/TASKS.md`
(which tracks a backlog item's *state*, not its content).

## Append-only, never edited in place

A requirement's history is worth keeping. Once an entry is written,
never edit or delete it to reflect a later change — append a new entry
that supersedes it instead (see below). This is the same discipline
`elm/REQUIREMENTS.md` shares with git itself: the record of what was
true *at the time* is the point.

## Entry schema

One entry per requirement, in this shape:

```markdown
### REQ-<AREA>-<N>

- **Status:** accepted | rejected | superseded by REQ-<AREA>-<M>
- **Stack:** <stack name from STACK.md, e.g. python-pytest>
- **Wording:** the exact requirement text, verbatim — the sentence that
  was actually judged, not a paraphrase.
- **INCOSE result:** which characteristic(s) it failed, if rejected
  (necessary / appropriate / unambiguous / complete / singular /
  feasible / verifiable / correct / conforming — see CLAUDE.md's
  "Requirements" section), or "passes all nine" if accepted.
- **Test(s):** file path(s) and test name(s), once red is confirmed
  (accepted requirements only — a rejected requirement has none).
- **Recorded:** <UTC timestamp>
```

A **rejected** entry still gets recorded — this is what lets
`BUSINESS.md`'s "Open questions" section point at *why* a requirement is
blocked rather than just noting that it is. Don't skip writing the
entry just because there's no test to attach.

## Superseding a requirement

When an accepted requirement's wording needs to change (not a bug in the
implementation — an actual change in what's required): write a **new**
entry with a new or the same ID as appropriate for the change's scope,
set its `Status` normally, and go back to amend the *old* entry's
`Status` line to `superseded by REQ-<AREA>-<M>` — this is the one
in-place edit this schema allows, since it's pointing forward rather
than rewriting history. Never delete the old entry's `Wording` or
`INCOSE result` — the point is to keep both versions readable.

## Commit convention

A commit touching `elm/REQUIREMENTS.md` is a ledger commit — it lives
inside the `elm/` submodule's own repository, reviewed by
`commit-reviewer` via `git -C elm diff --staged` (see AGENTS.md's
"Repository layout"), never bundled with a code-repo commit or an
`elm/ARCHITECTURE.md`/`elm/TASKS.md` change unless they're genuinely one
logical change (e.g., recording a rejected requirement is usually
`elm/REQUIREMENTS.md` alone; recording an accepted one alongside its
first test-file mention in `elm/TASKS.md` can be one commit if
`task-manager-specialist` already created that `elm/TASKS.md` row in the
same pass). Commit message: imperative mood, names the requirement ID
(e.g. "Record REQ-ENTRY-7 as accepted" or "Reject REQ-EXPORT-5:
ambiguous date-range wording") — same conventions as any other commit in
this project (`CLAUDE.md`'s "Commit conventions": no attribution lines).
