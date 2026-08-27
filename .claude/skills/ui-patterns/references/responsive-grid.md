# Responsive Grid

**Reach for it when:** content needs to remain usable across a range
of screen sizes without a hand-built layout for each one.

**Shape:** a column/breakpoint system that reflows content — more
columns and denser layout at wide viewports, fewer columns and stacked
content at narrow ones — driven by a small set of defined breakpoints,
not ad hoc per-screen adjustments.

**Contract notation:**
```
**Pattern:** Responsive Grid
**Breakpoints:** <e.g. mobile: 1 col, tablet: 2 col, desktop: 4 col>
**Reflow behavior:** <what gets hidden, collapsed, or reordered at narrow widths>
```

**Don't reach for it when** there's genuinely only one target form
factor (an internal tool used on one known desktop resolution) —
building adaptive behavior nobody will ever see is wasted work.
