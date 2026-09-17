---
description: Build a Loop OS contract from program.md — evaluator, draft, review, seal.
---

Build the first executable `contract.toml` for the current project from its
`program.md`. The program is the durable research plan; the contract is one
current execution frame. If `program.md` is missing, stop and run
`/loop-os:program` first.

Loop OS lives at `__LOOP_OS_HOME__`; instruments run by path from there. Let `$P`
be the absolute path of the current project. A complete sealed contract to model on
is `__LOOP_OS_HOME__/examples/delivery-round/contracts/gen1.toml`.

If `$P/.journal/` does not exist, say so and offer to run the bootstrap command
first — a contract can be drafted without a journal, but it cannot be sealed into
one that doesn't exist.

### 1. Explore frames, then translate the selected mechanism

Read and apply `__LOOP_OS_HOME__/references/frame-exploration.md` before choosing
the initial frame. Record the baseline and bounded candidate pass, then compare
and select. Use a draft file before bootstrap; once the journal exists, seal the
comparison as an `idea`. A null selection leaves the contract unsealed with the
missing evidence named. Do not execute candidate experiments during this step.

Read `program.md`, the repo (README, tests, existing metrics scripts), then
resolve — inferring what you can, asking the rest **in one batch**:

- **Objective** — one command that prints the quality of the current state as a
  single number on its last line. Which direction is better, and what target and
  margin make sense?
- **Mechanism** — *why* can that number move? One falsifiable paragraph. Press until
  there is an observation that would refute it; "the agent is smart" is not a
  mechanism.
- **Guards** — what must keep passing for an improvement to count? Include at least
  one guard that fails when the objective is gamed the obvious way (deleting work,
  weakening a test, shrinking the input).
- **Budget** — how many iterations may this generation spend, drawn up front and
  never refunded? Reuse an existing authorized budget or delegated decision
  authority; ask only if the necessary decision is still missing. Record why
  the chosen budget is defensible rather than inventing an unbounded default.

The program remains stable across generations. The first contract chooses one
initial frame from the compared candidates and its research question. Later frames
are successor contracts adopted through `/loop-os:jump`; do not rewrite the
program merely to make a frame pass.

Start from the program's existing evidence and required follow-ups. Name the
candidate or unfinished obligation this frame will advance. If choosing a new
direction instead, record why the inherited work is deferred or rejected.
Separate user requirements from working assumptions: a precaution introduced by
the agent is not automatically a new user mandate or approval boundary.

Also settle: `proxy_license` (which of the user's own words license the number as a
proxy for the real goal — if the number *is* the goal, say so explicitly) and
`integrity` pins (the evaluator plus every data surface a change could quietly
rewrite).

- **Core** — the `[core]` table is the contract's constitution: at minimum
  `core.goal`, one sentence stating what success means, in the user's words.
  Successors that preserve the constitution — `[core]` verbatim, plus the
  objectives' measurement fields, guards, and integrity pins — can be adopted
  with auto approval (`/loop-os:jump`); touching any of it forces the human
  gate. Freeze in `[core]` exactly what must survive every frame change — the
  goal, and any clause whose loosening would let future generations declare
  cheap victories. Sealing a contract without `[core]` is allowed but makes
  every future jump human-gated.

### 2. Build the evaluator if none exists

If no existing command prints the number, write one (e.g. `evaluate.py`) — smallest
thing that measures honestly, reading only committed project state. It goes into
`integrity`. Run it on the current commit and confirm the last line is one number.

### 3. Draft `$P/contract.toml`

Follow the README schema. Bind the reviewed program bytes in the contract:

```toml
[program]
path = "program.md"
digest = "<SHA-256 of the exact program.md bytes>"
```

Before sealing, include `# exploration: <note-id>; selected: <candidate-id>` as
a TOML comment referring to the sealed comparison. Match the frame mechanism and
first stage to the selected experiment. This is provenance, not a new schema field.

`aim` adds this path to integrity and emits a digest guard in every stage. A
program change between registration and aim is refused before a draw; a change
after aim is caught by the kernel guard. Every application guard must pass on
the current commit — run them.

### 4. Review before sealing — do not skip

The contract is the one artifact nothing else in the system re-checks: runs are
sealed against it, diagnoses are judged against it, and the jump path reviews only
its successor. Dispatch a subagent with the draft, the evaluator, the guard
commands, and the digest-verified exploration note body/id. Ask for a **defect list**:

- Objective command prints one number on its last line, on the current commit.
- `proxy_license` names a real licensing clause rather than restating the objective.
- Mechanism is falsifiable — name the observation that would refute it.
- Guards all pass now, and at least one fails under obvious gaming.
- **Integrity** pins cover the evaluator and every quietly-rewritable data surface.
- `[program]` binds the exact reviewed plan. Guards trace to a program constraint
  or an explicitly justified validity assumption; they do not silently redefine
  success or turn preparation into the goal.
- Existing candidates and required follow-ups have an explicit disposition.
- Apply the frame-exploration review checklist: candidate mechanisms are distinct,
  transfers state correspondences and break conditions, source/novelty uncertainty
  is explicit, and the selected experiment matches the contract. Alternatives and
  selection reasons must be present, including failure inversion and search limits.
- The diagnosis will report the program criterion, outcome/learning/preparation/
  no_change delta, remaining work, and the concrete next action.
- Budget is defensible as a multiple-testing contract.

Fix findings; re-review if the contract changed materially. Report unresolved
defects to the user instead of sealing over them.

### 5. Seal and report

```
uv run python os/seal.py contract --project $P --contract $P/contract.toml
```

Only a generation-1 contract (or the same generation re-registered) seals directly —
a higher generation is refused without a jump adoption, and that path is
deliberately not this command's job. Once a program is bound, changing or dropping
that binding also requires an adopted successor; re-registration cannot bypass
it. Report the contract digest, the objective's
current value, the drawn budget, and the next command in the cycle.
