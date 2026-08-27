# Card

**Reach for it when:** displaying a collection of similar items
(products, posts, users, files) where each needs to show a few key
facts and maybe a primary action, scannable at a glance.

**Shape:** a bounded visual unit (border, shadow, or background
separating it from its neighbors) repeated in a grid or list, each
instance identical in structure with different content.

**Contract notation:**
```
**Pattern:** Card
**Contains:** <what's shown on each card — image, title, key facts, action>
**Primary action:** <the card's main clickable/tappable behavior, if any>
**Density:** <compact | comfortable | spacious>
```

**Don't reach for it when** there's only one item, or items don't
actually share a shape — a card grid of dissimilar things looks
arbitrary rather than organized.
