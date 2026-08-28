---
name: ui-patterns
description: A curated toolbox of common visual/presentational UI patterns (Card, Modal/Overlay, Responsive Grid, Visual Hierarchy, Design Tokens, Navigation Bar/Sidebar, Interactive State Styling, Toast/Banner/Inline Alert, Data Table/List Density) for design-specialist to recognize and apply quickly when a requirement is about layout or presentation, instead of deriving the visual structure from scratch every time. Use this for how something looks and is visually organized — layout, spacing, color, component composition. Use ux-patterns instead for interaction and flow (what happens when, in what order). Check the symptom table first; load exactly one reference file for the pattern that matches. Do not use for backend component contracts — see design-patterns — or infrastructure — see stack-profiles.
---

# UI patterns

A shortcut for design-specialist's contract-definition step when a
requirement is about visual presentation rather than interaction flow:
recognize the layout/composition shape instead of deriving it from
scratch every time. Same reasoning as `design-patterns` and
`ux-patterns`, applied to the visual layer.

## Symptom → pattern

| If the requirement needs... | Reach for |
|---|---|
| a scannable collection of similar items, each showing a few key facts | Card |
| the user's focused attention on a short, bounded task without leaving the page | Modal / Overlay |
| a layout that adapts across phone, tablet, and desktop | Responsive Grid |
| one action on a screen to visibly outrank the others | Visual Hierarchy |
| spacing, color, and type to stay consistent as more screens get built | Design Tokens |
| a persistent, always-reachable way to switch between top-level sections | Navigation Bar / Sidebar |
| an interactive element to look different when hovered, focused, active, or disabled | Interactive State Styling |
| a status message with a visual severity and lifespan matching how urgent it is | Toast / Banner / Inline Alert |
| structured rows of data presented for fast, accurate scanning | Data Table / List Density |

Match on the leftmost column, not the pattern names — same caution as
the other two toolboxes.

## Using a pattern

1. Find the row that matches. Load `references/<pattern>.md` for that
   one pattern only.
2. Use its contract notation verbatim in `.elm/ARCHITECTURE.md`.
3. If nothing matches, describe the visual treatment directly — most
   layout decisions don't need a named pattern.

## Cross-cutting: visual accessibility isn't a pattern, it's a check

Every pattern here still needs sufficient color contrast (WCAG AA:
4.5:1 for body text, 3:1 for large text and UI components), a way to
distinguish state or meaning that doesn't rely on color alone (a
colorblind user can't see "red means error" if red is the only
signal), and touch targets large enough to hit reliably on mobile
(44x44pt is the usual floor). This is the visual half of accessibility;
the interaction half — keyboard navigation, screen readers — is
`ux-patterns`' cross-cutting note. A component often needs both.

## Don't force it

Same rule as the other two toolboxes: reach for a pattern because the
layout genuinely calls for it, not because naming one sounds more
designed. Three buttons all styled as "primary" isn't a Visual
Hierarchy problem solved differently, it's the pattern failing — see
that entry's own note.

## Scope

This toolbox is for visual layout and presentation — how something
looks and is composed, not what happens when or in what order. That's
`ux-patterns`. Backend component shape is `design-patterns`;
infrastructure shape is `stack-profiles`. A requirement often draws
from more than one: a settings page might need Progressive Disclosure
from `ux-patterns` for which fields show by default, and Card plus
Design Tokens from here for how each section is visually grouped —
record all of them in the same `.elm/ARCHITECTURE.md` entry.

Currently defined: `references/card.md`, `references/modal-overlay.md`,
`references/responsive-grid.md`, `references/visual-hierarchy.md`,
`references/design-tokens.md`, `references/navigation-bar-sidebar.md`,
`references/interactive-state-styling.md`,
`references/toast-banner-inline-alert.md`,
`references/data-table-list-density.md`. Add a new one the same way: a
reference file with the same four fields (reach for it when / shape /
contract notation / don't reach for it when), plus a row in the table
above.
