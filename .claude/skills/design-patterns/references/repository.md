# Repository

**Reach for it when:** code needs to read or write persistent data
without the rest of the system knowing or caring which storage
technology holds it.

**Shape:** an interface with find/save/delete-style methods; one
implementation per storage technology (Postgres, in-memory for tests,
S3, etc.).

**Contract notation:**
```
**Pattern:** Repository
**Interface:** <Entity>Repository.{find, save, delete}(...)
**Implementations:** <e.g. PostgresXRepository, InMemoryXRepository>
```

**Don't reach for it when** the data access is a single, simple query
used in one place — the abstraction costs more than it saves.
