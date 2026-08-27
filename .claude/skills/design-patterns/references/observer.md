# Observer

**Reach for it when:** one component's state change or event needs to
notify others, and the publisher shouldn't need to know who's
listening or how many.

**Shape:** a publish call plus N independent subscribers; a message
queue is often the Observer pattern realized at the infrastructure
layer.

**Contract notation:**
```
**Pattern:** Observer
**Event:** <what triggers a notification>
**Publisher:** <component>
**Subscribers:** <known consumers, if any are already defined>
```

**Don't reach for it when** there's exactly one consumer and it'll
stay that way — a direct call is simpler than a pub/sub layer.
