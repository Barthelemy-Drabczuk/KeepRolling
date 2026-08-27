# Navigation Bar / Sidebar

**Reach for it when:** multiple top-level sections need a persistent,
always-reachable way to switch between them.

**Shape:** a fixed structural element (top bar or side panel) listing
top-level destinations, with a clear visual indicator of which one is
currently active.

**Contract notation:**
```
**Pattern:** Navigation Bar / Sidebar
**Items:** <top-level destinations>
**Active state indication:** <how the current section is visually marked>
**Responsive behavior:** <e.g. sidebar collapses to a bottom bar or hamburger menu below a breakpoint>
```

**Don't reach for it when** there are only one or two top-level
sections — a navigation structure for two destinations is
over-engineering; a simple link or tab pair says the same thing with
less chrome.
