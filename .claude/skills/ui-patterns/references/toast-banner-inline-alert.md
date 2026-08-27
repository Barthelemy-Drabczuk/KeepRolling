# Toast / Banner / Inline Alert

**Reach for it when:** the system needs to communicate a status
message, and its urgency and scope should be visible from the
container it's shown in, not just its wording.

**Shape:** three tiers by placement and lifespan — a toast (transient,
corner, auto-dismisses, for low-stakes confirmations), a banner
(persistent, page-level, for something the user should notice but
isn't blocked by), and an inline alert (contextual, attached to the
specific field or section it's about).

**Contract notation:**
```
**Pattern:** Toast / Banner / Inline Alert
**Severity:** <info | success | warning | error>
**Placement:** <toast | banner | inline>
**Auto-dismiss:** <if toast, after how long — omit for banner/inline>
```

**Don't reach for a toast** when the message is something the user
must see and act on — it can disappear before they read it. That's
what a banner or inline alert is for.
