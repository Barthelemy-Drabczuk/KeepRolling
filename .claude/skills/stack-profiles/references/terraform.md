# Terraform profile

**Location & naming:** infrastructure lives under `infra/`, split into
`infra/modules/<name>/` (reusable components) and `infra/envs/<env>/`
(per-environment root configs — `dev`, `staging`, `prod`). Tests live
alongside what they test as `<name>.tftest.hcl`, using Terraform's
native test framework (`terraform test`, Terraform 1.6+).

**Red confirmation:** write a `.tftest.hcl` `run` block asserting the
property the requirement describes, and run `terraform test` from the
module or env directory the resource belongs to. Prefer
`command = "plan"` in the run block over `"apply"` wherever the
assertion can be checked from a plan alone — it's fast, free, and
doesn't touch real infrastructure, which matters far more here than in
a code test suite. A new test must fail because the resource or
property doesn't exist yet, not because of an HCL syntax error or a
missing provider/variable — `terraform validate` should already have
ruled those out before you call anything red.

For a requirement that's really a policy ("no public S3 buckets",
"every resource has a cost-center tag") rather than one specific
resource, a failing Checkov/tfsec/OPA check is the equivalent red
state — use whichever policy tool this project already has configured
rather than writing a `.tftest.hcl` for something a policy scan already
covers.

**Verify commands, in order:**
1. `terraform fmt -check -recursive` — from the repo root.
2. `terraform validate` — from each module/env directory touched.
3. `tflint` — from each directory touched, if configured.
4. `terraform test` — from each module/env directory touched, full set
   of `.tftest.hcl` files in it.
5. `checkov` / `tfsec` (whichever this project has configured) —
   policy/security scan, from the repo root.

`terraform plan` against real state is **not** a default verify step.
Run it only if this environment actually has the relevant cloud
credentials configured, and report its absence as "skipped" — never as
"passed." Silently treating a skipped plan as green is worse than not
attempting it.

**Cautions, unique to this stack:**
- **Blast radius.** Unlike a code change, an infra apply can be
  destructive — a resource replace or delete that no revert commit can
  undo (data in a deleted database, a queue torn down with messages in
  flight). If a plan implies `-/+` or `-` against anything, surface
  that explicitly in the verdict, not as a line item in an otherwise
  clean report.
- **Test-per-resource doesn't scale the way test-per-behavior does.**
  One policy or `.tftest.hcl` file legitimately covers a whole class of
  resources; don't force a 1:1 mapping the way Python's TDD loop
  implies.
- **Not everything is cheap to check locally.** Some verify steps
  (mainly `plan`) need live cloud credentials this environment may not
  have. Degrade gracefully: report what you could check and what you
  couldn't, rather than assuming credentials exist.
