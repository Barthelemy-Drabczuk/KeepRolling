# Stack map

Which technology stack owns which part of the repo. Agents consult
this — via the `stack-profiles` skill — before running any
red-confirmation, verify, or lint/format command, instead of assuming
one language's tooling applies everywhere.

| Path prefix | Stack | Profile |
|---|---|---|
| `src/frontend/` | python-frontend | `stack-profiles/references/python-frontend.md` |
| `src/backend/` | python | `stack-profiles/references/python.md` |
| `infra/` | terraform | `stack-profiles/references/terraform.md` |
| `.github/workflows/` | github-actions | `stack-profiles/references/github-actions.md` |

`src/frontend/` and `src/backend/` are siblings under `src/`, not one
nested inside the other — same language and tooling as `python`, but
`python-frontend` exists as its own profile because "red"/"verify"/
"green" mean something narrower there — see that profile before
assuming a passing/failing frontend test proves what it would for a
backend one.

`github-actions` is unlike the other three rows: nothing in this repo
can execute or observe a workflow run locally, so its profile's
"verify" step is manual (open a PR, observe the check run, deliberately
break something, observe it fail, revert) rather than a local command
sequence — see that profile before assuming a green/red result here
comes from a command the way it does for `python` or `terraform`.

Add a row here whenever a new stack enters the repo, and a matching
`stack-profiles/references/<stack>.md`.
