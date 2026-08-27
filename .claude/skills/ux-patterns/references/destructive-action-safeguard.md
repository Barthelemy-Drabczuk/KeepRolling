# Destructive Action Safeguard

**Reach for it when:** an action deletes, cancels, or otherwise can't
be trivially undone, and a stray click would cost the user real data
or effort.

**Shape:** two competing approaches — a confirmation dialog that
blocks until the user explicitly confirms, or an undo toast that lets
the action happen immediately but stays reversible for a short window.
Prefer undo for frequent, low-blast-radius actions (archiving an
email, deleting a list item); reserve blocking confirmation for rare,
high-consequence ones (deleting an account). Confirmation dialogs used
too often train users to click through them without reading.

**Contract notation:**
```
**Pattern:** Destructive Action Safeguard
**Action:** <what's being protected>
**Approach:** confirm-then-act | act-then-undo
**Undo window:** <if act-then-undo, how long the action stays reversible>
```

**Don't reach for it when** the action is trivially reversible already
(re-adding an item to a list) — a safeguard just adds friction to
something that was never risky.
