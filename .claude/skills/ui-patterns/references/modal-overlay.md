# Modal / Overlay

**Reach for it when:** the user's focused attention is needed for a
short, bounded task or decision, without navigating away from their
current context.

**Shape:** content presented above the current screen, dimming or
blocking interaction with what's behind it, with an explicit way to
dismiss.

**Contract notation:**
```
**Pattern:** Modal / Overlay
**Triggers:** <what opens it>
**Contains:** <the focused task/content inside>
**Dismissal:** <X button, backdrop click, Esc, explicit action only — which are allowed>
```

**Don't reach for it when** the task is long or exploratory
(multi-step onboarding, a full settings panel) — modals trap users in
a small stacked context; a full page or a slide-out drawer serves a
long task better. Stacking a modal on top of a modal is a sign this
pattern got reached for one layer too many times.
