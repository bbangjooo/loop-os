# Full-auto mode

Full-auto is an opt-in authority profile for the agent harness. It changes who
may decide constitutional jumps and journal recovery; it does not remove the
files, reviews, digests, budgets, guards, or anchors that make those decisions
auditable.

## Compatibility contract

- Default projects are unchanged. Without `.loop-os-full-auto.json`, ordinary
  jumps retain deterministic auto approval and constitutional jumps retain the
  human gate.
- `os/autonomy.py enable` writes the tracked grant and appends
  `autonomy_changed.v1` when the journal is healthy. Existing readers replay
  that additive event without changing their current state projection.
- `os/jump.py` accepts `mode=full_auto` only with a valid grant, an independent
  PASS review, and a structured agent decision. Existing human and ordinary
  auto approval files remain valid.
- `os/autonomy.py recover` archives the original journal, anchor, decision, and
  grant under `.journal/recovery/`, accepts the readable current event payloads
  as a new trust boundary, rebuilds their chain links, appends
  `journal_recovered.v1`, and writes a new tracked anchor. Invalid records stay
  in the archive and are listed by line digest in the recovery event.

The recovery operation is retry-safe for a partially created archive: matching
bytes are reused and conflicting bytes are refused. The journal rewrite itself
is atomic. A crash after the rewrite but before the recovery event leaves the
first archive intact; the next recovery pass archives the new current bytes and
creates the missing explicit trust boundary.

## Forward and rollback paths

Forward:

```bash
uv run python os/autonomy.py enable --project "$P" \
  --approved-by "user invoking loop-os full-auto" \
  --statement "delegate constitutional jumps, journal recovery, and continuous goal execution to the agent"
```

Rollback does not rewrite prior decisions. It disables future use and records
the change when the journal is healthy:

```bash
uv run python os/autonomy.py disable --project "$P" --reason "return to governed mode"
```

After rollback, old full-auto adoption and recovery events remain part of the
evidence chain. New constitutional jumps again require human approval.

## Boundary

This mode operates only inside permissions already granted to the Codex or
Claude harness. It cannot override host sandboxing, account limits, deployment
policy, release authority, capital allocation, or live-trading boundaries.
