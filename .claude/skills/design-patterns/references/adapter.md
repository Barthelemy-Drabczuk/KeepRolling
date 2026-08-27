# Adapter

**Reach for it when:** an external library, legacy module, or
third-party API has an interface that doesn't match what the rest of
the system expects.

**Shape:** a thin wrapper implementing your own interface, delegating
every call to the external one underneath.

**Contract notation:**
```
**Pattern:** Adapter
**Interface:** <your interface>
**Wraps:** <external library/API>
**Translation notes:** <anything non-obvious about the mapping>
```

**Don't reach for it when** you control both sides — just make them
match instead of adapting between them.
