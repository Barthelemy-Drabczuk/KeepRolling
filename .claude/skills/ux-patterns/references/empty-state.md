# Empty State

**Reach for it when:** a view can legitimately show zero items — first
use, an empty inbox, no search results, a newly created but
unpopulated workspace.

**Shape:** replace the blank space with a short explanation of why
it's empty and one clear next action, not just an absent list.

**Contract notation:**
```
**Pattern:** Empty State
**View:** <which screen/list this applies to>
**Message:** <why it's empty, in the user's terms>
**Next action:** <the one thing they can do from here>
```

**Don't reach for it when** the view is never actually empty in
practice — don't design for a case that can't occur.
