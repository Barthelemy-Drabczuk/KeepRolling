# Progressive Disclosure

**Reach for it when:** a screen or form has fields/options that only a
minority of users need, and showing all of them upfront would
overwhelm the common case.

**Shape:** show the common/required inputs by default; put the rest
behind an explicit "more options" or "advanced" control, never hidden
without a visible way to reveal it.

**Contract notation:**
```
**Pattern:** Progressive Disclosure
**Always visible:** <fields/options everyone needs>
**Revealed on demand:** <fields/options behind "more" — and what reveals them>
```

**Don't reach for it when** hiding something means most users will
never find it and actually need it — that's not disclosure, that's
burial.
