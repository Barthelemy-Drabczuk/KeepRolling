# Breadcrumb Navigation

**Reach for it when:** content sits in a hierarchy more than two
levels deep and users need to understand where they are and jump back
up without repeated "back" clicks.

**Shape:** a horizontal trail of ancestor links from the root down to
the current location, each one clickable except the current page
itself.

**Contract notation:**
```
**Pattern:** Breadcrumb Navigation
**Hierarchy:** <root -> ... -> current, the levels that exist>
**Truncation:** <how a very deep path is shortened, if at all>
```

**Don't reach for it when** the hierarchy is only one or two levels
deep — a back button or a simple tab bar says the same thing with less
chrome.
