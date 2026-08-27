---
name: ux-patterns
description: A curated toolbox of common UI/UX interaction patterns (Progressive Disclosure, Wizard/Stepper, Optimistic UI, Empty State, Skeleton Screen, Inline Validation, Destructive Action Safeguard, Master-Detail, Breadcrumb Navigation) for design-specialist to recognize and apply quickly when a requirement is user-facing, instead of deriving an interaction from scratch every time. Use this whenever design-specialist is defining a contract for a screen, flow, or form — anything a user directly sees or operates. Check the symptom table first; load exactly one reference file for the pattern that matches. Do not use for backend component contracts — see design-patterns — visual layout and presentation — see ui-patterns — or infrastructure — see stack-profiles.
---

# UX patterns

A shortcut for design-specialist's contract-definition step when a
requirement is user-facing: recognize the interaction shape instead of
deriving it from scratch every time. Same reasoning as `design-patterns`,
applied one layer up — at the screen/flow level instead of the
code-structure level.

## Symptom → pattern

| If the requirement needs... | Reach for |
|---|---|
| to hide options most users don't need, without removing them entirely | Progressive Disclosure |
| a complex task broken into ordered, digestible steps | Wizard / Stepper |
| an action to feel instant despite a server round-trip | Optimistic UI |
| a view that can legitimately show zero items | Empty State |
| a loading view where the eventual layout is already known | Skeleton Screen |
| a form to catch mistakes before the user hits submit | Inline Validation |
| protection against an accidental delete/cancel/other irreversible action | Destructive Action Safeguard |
| scanning many items while inspecting one closely, repeatedly | Master-Detail |
| users to understand and backtrack their place in a deep hierarchy | Breadcrumb Navigation |

Match on the leftmost column, not the pattern names — same caution as
`design-patterns`: naming the pattern first tends to bend the
requirement to fit it.

## Using a pattern

1. Find the row that matches. Load `references/<pattern>.md` for that
   one pattern only.
2. Use its contract notation verbatim in `elm/ARCHITECTURE.md`. Same
   reasoning as the software toolbox: shorter than prose, and
   consistent for whoever builds the screen.
3. If nothing matches, describe the interaction directly — most UI
   requirements are simple enough not to need a named pattern.

## Cross-cutting: accessibility isn't a pattern, it's a check

Every pattern selected here still has to work for keyboard-only
navigation, a screen reader, and adequate color contrast — that's not
an alternative pattern, it's a property every choice above needs to
have. A pattern applied inaccessibly hasn't actually satisfied the
requirement; note it as a gap in the contract rather than letting it
pass silently.

## Don't force it

Same rule as `design-patterns`: reach for a pattern because the
interaction genuinely calls for it, not because naming one sounds more
designed. A wizard for a three-field form, or a master-detail view for
a list of four items, is friction dressed up as structure.

## Scope

This toolbox is for interaction and flow — how a user accomplishes a
task, not what it looks like doing it. Visual layout and presentation
(cards, modals, spacing, color) is `ui-patterns`; backend component
shape is `design-patterns`; infrastructure shape is `stack-profiles`.
A single requirement can need more than one: a password-reset flow
might draw a Wizard/Stepper from here, a Modal from `ui-patterns` for
how each step is presented, and a Strategy for the notification
channel from `design-patterns` — record all of them in the same
`elm/ARCHITECTURE.md` entry rather than splitting the component across
several.

Currently defined: `references/progressive-disclosure.md`,
`references/wizard-stepper.md`, `references/optimistic-ui.md`,
`references/empty-state.md`, `references/skeleton-screen.md`,
`references/inline-validation.md`,
`references/destructive-action-safeguard.md`,
`references/master-detail.md`, `references/breadcrumb-navigation.md`.
Add a new one the same way: a reference file with the same four fields
(reach for it when / shape / contract notation / don't reach for it
when), plus a row in the table above.
