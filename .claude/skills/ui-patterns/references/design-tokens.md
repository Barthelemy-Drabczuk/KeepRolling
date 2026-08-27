# Design Tokens

**Reach for it when:** a growing set of screens or components is
starting to drift visually — inconsistent spacing, ad hoc colors,
one-off font sizes — because each was styled independently.

**Shape:** a small, named, reusable set of values (a spacing scale, a
color-role palette, a type scale) that every component references
instead of hardcoding its own numbers.

**Contract notation:**
```
**Pattern:** Design Tokens
**Scale(s) used:** <which spacing/color/type tokens this component draws from>
**New tokens needed:** <anything this component needs that doesn't exist yet — flag for design-system review rather than inventing one inline>
```

**Don't reach for a new token** when an existing one already fits
closely enough — introducing a near-duplicate value (15px next to an
existing 16px token) is exactly the drift this pattern exists to
prevent.
