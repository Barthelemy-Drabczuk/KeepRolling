# Stack map

Which technology stack owns which part of the repo. Agents consult
this — via the `stack-profiles` skill — before running any
red-confirmation, verify, or lint/format command, instead of assuming
one language's tooling applies everywhere.

| Path prefix | Stack | Profile |
|---|---|---|
| `backend/app/frontend/` | python-frontend | `stack-profiles/references/python-frontend.md` |
| `backend/` | python | `stack-profiles/references/python.md` |
| `infra/` | terraform | `stack-profiles/references/terraform.md` |

Prefixes are matched most-specific-first: `backend/app/frontend/`'s row
wins over the broader `backend/` row for anything under it. Same
language and tooling as `python`, but `python-frontend` exists as its
own profile because "red"/"verify"/"green" mean something narrower
there — see that profile before assuming a passing/failing frontend
test proves what it would for a backend one.

Add a row here whenever a new stack enters the repo, and a matching
`stack-profiles/references/<stack>.md`.
