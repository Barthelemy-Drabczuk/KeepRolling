# Facade

**Reach for it when:** a common task requires orchestrating several
subsystems, and callers shouldn't need to know about all of them
individually.

**Shape:** one method (or a small class) that calls the subsystems in
the right order and returns a single result; the subsystems themselves
stay unchanged and independently usable.

**Contract notation:**
```
**Pattern:** Facade
**Interface:** <the simplified entry point>
**Orchestrates:** <subsystem A>, <subsystem B>, ...
```

**Don't reach for it when** there's only one subsystem involved —
that's not a facade, it's just calling the thing.
