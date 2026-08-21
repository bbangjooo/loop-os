---
description: Report where the current Loop OS project stands — chain health, budget, and the next required action.
---

Report the state of the current project. **Read-only** — seal nothing, aim at
nothing, run nothing.

Loop OS lives at `__LOOP_OS_HOME__`; run instruments by path from there. Let `$P`
be the absolute path of the current project.

```
uv run python os/journal.py verify --project $P
uv run python os/journal.py status --project $P
uv run python os/steer.py frame-health --project $P
```

If `$P/.journal/` does not exist, say the project is not bootstrapped and point at
the bootstrap command instead of running anything else.

Then summarize for the user:

- **Chain** — verified, or exactly how it is broken (this is the one finding worth
  interrupting for).
- **Frame** — generation, hypothesis class, and how many REJECTED diagnoses it has
  accumulated.
- **Budget** — iterations drawn and remaining in this generation.
- **Next action** — the `next_required` value, as the concrete command to run.
- **Frame health** — the three interpretation requests, quoted as questions. Do not
  answer them here; answering them is part of a cycle, and the answers must be
  recorded as notes.
