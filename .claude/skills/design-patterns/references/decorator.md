# Decorator

**Reach for it when:** one cross-cutting behavior (caching, retry,
logging, rate limiting) needs to wrap a component without modifying
the component itself, and might need to be added or removed
independently of it.

**Shape:** implements the same interface as what it wraps, delegates
the call through, and adds exactly one extra behavior before or after.

**Contract notation:**
```
**Pattern:** Decorator
**Interface:** <shared interface with the wrapped component>
**Wraps:** <component being decorated>
**Adds:** <the one behavior this decorator contributes>
```

**Don't reach for it when** the behavior is core to the component's
job, not incidental to it — put it in the component.
