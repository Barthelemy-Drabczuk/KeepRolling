# Master-Detail

**Reach for it when:** users need to scan many items and inspect one
closely, repeatedly, without losing their place in the list each time.

**Shape:** a list/overview pane alongside a detail pane for whatever's
selected; selecting a different item updates the detail pane in place
rather than navigating away from the list.

**Contract notation:**
```
**Pattern:** Master-Detail
**List shows:** <what's in the overview pane, per item>
**Detail shows:** <what's in the detail pane for the selected item>
**Selection persistence:** <does the selected item stay selected across a refresh/reload?>
```

**Don't reach for it when** items are rarely compared or revisited —
a simple list-then-full-page-detail is less UI to build and reason
about.
