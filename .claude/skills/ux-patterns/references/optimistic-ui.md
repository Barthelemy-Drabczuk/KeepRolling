# Optimistic UI

**Reach for it when:** an action's outcome is highly predictable and
reversible, and waiting for a server round-trip before updating the
screen would make a fast action feel slow.

**Shape:** update the UI immediately as if the action succeeded;
reconcile silently on server confirmation, and roll back with a
visible, specific explanation if it actually failed.

**Contract notation:**
```
**Pattern:** Optimistic UI
**Action:** <what the user does>
**Immediate UI change:** <what updates before confirmation>
**Rollback behavior:** <what happens, and what the user sees, if the server rejects it>
```

**Don't reach for it when** failure is common or the action is hard to
explain after the fact (payments, anything with real-world side
effects outside the app) — show a real pending state and wait for
confirmation instead.
