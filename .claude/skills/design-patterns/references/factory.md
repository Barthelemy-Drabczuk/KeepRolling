# Factory

**Reach for it when:** a caller needs an instance of one of several
related types, chosen by a config value or input, without needing to
know the concrete type.

**Shape:** a single `create(kind)` function/method that returns the
shared interface type; the concrete type is an implementation detail
the caller never sees.

**Contract notation:**
```
**Pattern:** Factory
**Interface:** <shared return type>
**create(kind):** <input> -> <Interface>
**Known kinds:** <A>, <B>, <C>
```

**Don't reach for it when** the concrete type is always known at the
call site — that's just calling the constructor directly.
