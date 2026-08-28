---
name: design-patterns
description: A curated toolbox of common software design patterns (Strategy, Factory, Builder, Adapter, Decorator, Facade, Observer, Chain of Responsibility, Repository) for design-specialist to recognize and apply quickly instead of deriving a component's shape from scratch every time. Use this whenever design-specialist is defining a contract for a software component. Check the symptom table first; load exactly one reference file for the pattern that matches, not all of them. Do not use for infrastructure contracts — a Terraform resource's shape isn't a GoF pattern question, see the stack-profiles skill instead.
---

# Design patterns

A shortcut for design-specialist's contract-definition step: recognize
the shape a component needs instead of deriving it from first
principles every time. Faster to write, and the pattern name itself
carries structure — "Strategy" conveys more than a paragraph of prose
describing the same thing, for you and for whoever reads
`.elm/ARCHITECTURE.md` later.

## Symptom → pattern

| If the component needs... | Reach for |
|---|---|
| several interchangeable ways to do the same thing, chosen at runtime | Strategy |
| an instance of one of several types, chosen by config/input, without the caller knowing which | Factory |
| assembly from many optional parts, or steps that must happen in order | Builder |
| to wrap a third-party/legacy interface that doesn't match your own | Adapter |
| one cross-cutting behavior (caching, retry, logging) added around it, independently of it | Decorator |
| one simple entry point in front of several subsystems | Facade |
| to notify others of a state change without knowing who's listening | Observer |
| an ordered sequence of handlers, each of which may act or pass along | Chain of Responsibility |
| to read/write persistent data without the rest of the system knowing the storage technology | Repository |

Match on the leftmost column, not the pattern names — two different
requirements can both smell like "Factory" for different reasons, and
picking the name first tends to bend the requirement to fit it instead
of the other way around.

## Using a pattern

1. Find the row that matches. Load `references/<pattern>.md` for that
   one pattern only — not the others.
2. Use its contract notation verbatim in `.elm/ARCHITECTURE.md`, filled
   in for this component. It's shorter than prose and consistent
   across the codebase.
3. If nothing matches, that's fine — most contracts are plain interface
   signatures. A pattern name isn't required just because this skill
   exists.

## Don't force it

Reach for a pattern because the shape already fits, not because naming
one sounds rigorous. A Strategy interface with exactly one
implementation, or a Factory that only ever returns one type, is
unnecessary indirection — flag that instead of defaulting to it. Two
genuinely interchangeable implementations that exist *now*, not "might
exist later," is the usual bar.

This also feeds step 3 of design-specialist's own process (checking for
drift): if an existing component already implements one of these
patterns and a new requirement fits the same shape, reuse it — a second
ad-hoc structure solving the same problem a pattern already solves
elsewhere is exactly the duplication that check exists to catch.

## Scope

This toolbox is for software component contracts. An infrastructure
contract's shape question is usually simpler — one resource, a small
module, or a policy — not a GoF pattern; see the `stack-profiles` skill
for that side of a contract instead.

Currently defined: `references/strategy.md`, `references/factory.md`,
`references/builder.md`, `references/adapter.md`,
`references/decorator.md`, `references/facade.md`,
`references/observer.md`, `references/chain-of-responsibility.md`,
`references/repository.md`. Add a new one the same way: a reference
file with the same four fields (reach for it when / shape / contract
notation / don't reach for it when), plus a row in the table above.
