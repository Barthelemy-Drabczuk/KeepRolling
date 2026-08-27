# Wizard / Stepper

**Reach for it when:** a task requires collecting distinct kinds of
information across ordered stages, or has steps that genuinely depend
on the previous one being done first.

**Shape:** sequential steps with visible progress, one focused task
per step, and a clear way to go back without losing what was already
entered.

**Contract notation:**
```
**Pattern:** Wizard/Stepper
**Steps, in order:** <step1>, <step2>, <step3> (mark any skippable ones)
**Progress indication:** <how the user sees where they are and how many remain>
**Exit/resume:** <can they leave partway and come back? is progress saved?>
```

**Don't reach for it when** the steps have no real dependency on each
other — that's just a form with sections, and a single scrollable page
is less friction than forced pagination.
