# Chain of Responsibility

**Reach for it when:** a request needs to pass through an ordered
sequence of handlers, each of which may act on it, modify it, or pass
it along.

**Shape:** linked handlers, each with a "handle this or pass it on"
decision; the caller only ever talks to the first handler.

**Contract notation:**
```
**Pattern:** Chain of Responsibility
**Interface:** <handler>.<handle>(<request>) -> <request | result>
**Handlers, in order:** <A>, <B>, <C>
```

**Don't reach for it when** the steps are fixed and never
conditionally skipped — that's just a function calling other functions
in sequence.
