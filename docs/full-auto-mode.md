# Full-auto mode

Full-auto is an opt-in project policy consumed by the existing Loop OS skill. It changes who
may decide constitutional jumps and journal recovery; it does not remove the
files, reviews, digests, budgets, guards, or anchors that make those decisions
auditable.

## Compatibility contract

- Default projects are unchanged. Without `.loop-os/config.toml` in full-auto mode, ordinary
  jumps retain deterministic auto approval and constitutional jumps retain the
  human gate.
- `os/autonomy.py enable` writes the tracked `.loop-os/config.toml` and appends
  `autonomy_changed.v1` when the journal is healthy. Existing readers replay
  that additive event without changing their current state projection.
- `os/jump.py` accepts `mode=full_auto` only with a valid config, an independent
  PASS review, and a structured agent decision. Existing human and ordinary
  auto approval files remain valid.
- `os/autonomy.py recover` archives the original journal, anchor, decision, and
  config under `.journal/recovery/`, accepts the readable current event payloads
  as a new trust boundary, rebuilds their chain links, appends
  `journal_recovered.v1`, and writes a new tracked anchor. Invalid records stay
  in the archive and are listed by line digest in the recovery event.

The recovery operation is retry-safe for a partially created archive: matching
bytes are reused and conflicting bytes are refused. The journal rewrite itself
is atomic. A crash after the rewrite but before the recovery event leaves the
first archive intact; the next recovery pass archives the new current bytes and
creates the missing explicit trust boundary.

## Forward and rollback paths

The config is harness-neutral, so Codex and Claude consume the same policy:

```toml
schema = "loop-os-config-v1"

[autonomy]
mode = "full_auto"
constitutional_jumps = "agent"
journal_recovery = "agent"
continue_until = "external_goal"
independent_review = true

[autonomy.grant]
approved_by = "operator"
statement = "delegate Loop OS autonomy to the agent"
granted_at = "2026-08-25T00:00:00Z"
```

Full-auto does not turn preparation into completion. Program-bound contracts
require a `program_progress` block in each newly issued run's diagnosis; see
[the binding and progress contract](program-progress.md). A reported `outcome`
is an author declaration, not an OS verdict that the external goal is achieved.
Use the frame-health program questions to catch preparation detours, unresolved
prerequisites and forgotten inherited work. Changes to `[program]` use the
existing constitutional approval path, even when `[core]` text stays unchanged.

The equivalent instrument-managed forward path is:

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

## Legacy migration

`.loop-os-full-auto.json` remains readable for one compatibility window. Run:

```bash
uv run python os/autonomy.py migrate --project "$P"
```

Migration writes `.loop-os/config.toml` first, verifies it, and preserves the
legacy JSON with `enabled=false` plus migration provenance. New readers always
prefer the TOML config; old readers therefore fail safe into governed mode.
Migration is idempotent and rollback never rewrites prior journal evidence.

## Boundary

This mode operates only inside permissions already granted to the Codex or
Claude harness. It cannot override host sandboxing, account limits, deployment
policy, release authority, capital allocation, or live-trading boundaries.
