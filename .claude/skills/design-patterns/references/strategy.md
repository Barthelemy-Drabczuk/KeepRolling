# Strategy

**Reach for it when:** multiple interchangeable ways to perform the
same operation need to be selected at runtime (pricing rules, auth
methods, notification channels), and the set of options can grow
without changing the caller.

**Shape:** one interface with a single clear method, N concrete
implementations, and a selector that picks which one to use (a config
value, a factory, or dependency injection).

**Contract notation:**
```
**Pattern:** Strategy
**Interface:** <Name>.<method>(<args>) -> <return>
**Implementations:** <A>, <B>, <C>
**Selector:** <what decides which implementation runs>
```

**Don't reach for it when** there's only one implementation today and
no concrete second one planned — that's just a function.
