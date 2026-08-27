# Skeleton Screen

**Reach for it when:** content takes a moment to load and the eventual
layout is already known — a spinner tells the user to wait, a
skeleton tells them what's coming.

**Shape:** a low-fidelity placeholder shaped like the real content
(blocks where text and images will appear), replaced in place once
data arrives — never a full-page spinner for a partially-known layout.

**Contract notation:**
```
**Pattern:** Skeleton Screen
**View:** <which screen/component>
**Placeholder shape:** <what the skeleton mimics — text lines, image blocks, card outlines>
```

**Don't reach for it when** the load is near-instant (it just
flickers) or the eventual layout is genuinely unknown until data
arrives — use a spinner instead.
