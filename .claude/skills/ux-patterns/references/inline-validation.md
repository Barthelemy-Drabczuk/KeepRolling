# Inline Validation

**Reach for it when:** a form field has a clear, checkable validity
rule and catching a mistake early saves the user a failed-submit round
trip.

**Shape:** validate a field as the user finishes it (on blur, or live
for format rules like matching passwords), show the specific problem
next to the field, never only at submit.

**Contract notation:**
```
**Pattern:** Inline Validation
**Field:** <which field>
**Rule:** <what makes it valid>
**Trigger:** <on blur / as-typed / on submit-then-live>
**Message:** <what the user sees when it's invalid>
```

**Don't reach for it when** the rule can only be checked server-side
after submission (e.g., "is this email already registered") — validate
those on submit and say so, rather than faking a client-side check.
