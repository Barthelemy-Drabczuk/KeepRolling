# Interactive State Styling

**Reach for it when:** an interactive element has only been designed
in its default appearance, and users have no visual signal for hover,
focus, being pressed, or being unavailable.

**Shape:** an explicit, distinct visual treatment for each state a
component can actually be in — hover, focus (especially for keyboard
users), active/pressed, disabled, and loading where relevant.

**Contract notation:**
```
**Pattern:** Interactive State Styling
**Component:** <what this applies to>
**States defined:** <hover, focus, active, disabled, loading — which apply and how each differs from default>
```

**Don't reach for it as decoration** when a state change doesn't
correspond to anything real — an animated hover effect on plain static
text serves no purpose. Every state should communicate something true
about interactivity, not just add motion.
