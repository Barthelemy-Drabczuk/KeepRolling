# Builder

**Reach for it when:** constructing one object needs several optional
parameters, or the construction steps have an order/validation a
single constructor call can't express cleanly.

**Shape:** a step-by-step assembler that accumulates state across
calls and returns the finished, validated object only at the end.

**Contract notation:**
```
**Pattern:** Builder
**Product:** <the object being built>
**Steps:** <step1>, <step2>, ... (note which are required vs optional)
**Build():** returns <Product>, validated
```

**Don't reach for it when** the object has two or three required
fields — a plain constructor is clearer.
