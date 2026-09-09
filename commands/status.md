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
uv run python os/autonomy.py status --project $P
```

If `$P/.journal/` does not exist, point at `/loop-os:program` when the program is
missing, otherwise `/loop-os:bootstrap`. For an existing journal, always report
its pending work. A legacy project without a program binding is `UNBOUND`, not
a reason to abandon or restart its issued runs. Bind a reviewed program in a
later contract, using the applicable adoption path; do not rewrite old evidence.

Then summarize for the user:

- **Program** — pinned path/digest and whether the file still matches; the latest
  declared criterion/delta, remaining work, and next action. Report outcome,
  learning, preparation and no_change separately. Missing reports mean unknown.
  `completion: NOT_EVALUATED` is deliberate: the application still owns the
  external completion proof. Do not present report counts as achieved outcomes.
- **Chain** — verified, or exactly how it is broken (this is the one finding worth
  interrupting for).
- **Frame** — generation, hypothesis class, and how many REJECTED diagnoses it has
  accumulated.
- **Budget** — iterations drawn and remaining in this generation.
- **Next action** — the `next_required` value, as the concrete command to run.
- **Frame health** — the frame and program interpretation requests. Do not
  answer them here; answering them is part of a cycle, and the answers must be
  recorded as notes.
- **Autonomy** — governed or full_auto, the config source, and whether legacy JSON
  migration is still pending.
