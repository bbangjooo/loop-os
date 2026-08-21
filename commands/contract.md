---
description: Build a Loop OS contract from a plain-language problem statement — interview, evaluator, draft, review, seal.
---

Build `contract.toml` for the current project from the user's problem statement.
If they gave one as an argument, start from it; otherwise ask for it first — one
sentence about what they want to get better is enough to begin.

Loop OS lives at `__LOOP_OS_HOME__`; instruments run by path from there. Let `$P`
be the absolute path of the current project. A complete sealed contract to model on
is `__LOOP_OS_HOME__/examples/delivery-round/contracts/gen1.toml`.

If `$P/.journal/` does not exist, say so and offer to run the bootstrap command
first — a contract can be drafted without a journal, but it cannot be sealed into
one that doesn't exist.

### 1. Translate the problem into the four contract questions

Read the repo (README, tests, existing metrics scripts), then resolve — inferring
what you can, asking the rest **in one batch**:

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
  never refunded? Make the user pick a number they can defend, not a comfortable
  default.

Also settle: `proxy_license` (which of the user's own words license the number as a
proxy for the real goal — if the number *is* the goal, say so explicitly) and
`integrity` pins (the evaluator plus every data surface a change could quietly
rewrite).

### 2. Build the evaluator if none exists

If no existing command prints the number, write one (e.g. `evaluate.py`) — smallest
thing that measures honestly, reading only committed project state. It goes into
`integrity`. Run it on the current commit and confirm the last line is one number.

### 3. Draft `$P/contract.toml`

Follow the README schema. Every guard must pass on the current commit — run them.

### 4. Review before sealing — do not skip

The contract is the one artifact nothing else in the system re-checks: runs are
sealed against it, diagnoses are judged against it, and the jump path reviews only
its successor. Dispatch a subagent with the draft, the evaluator, and the guard
commands, and ask for a **defect list**, not an opinion:

- Objective command prints one number on its last line, on the current commit.
- `proxy_license` names a real licensing clause rather than restating the objective.
- Mechanism is falsifiable — name the observation that would refute it.
- Guards all pass now, and at least one fails under obvious gaming.
- Integrity pins cover the evaluator and every quietly-rewritable data surface.
- Budget is defensible as a multiple-testing contract.

Fix findings; re-review if the contract changed materially. Report unresolved
defects to the user instead of sealing over them.

### 5. Seal and report

```
uv run python os/seal.py contract --project $P --contract $P/contract.toml
```

Only a generation-1 contract (or the same generation re-registered) seals directly —
a higher generation is refused without a jump adoption, and that path is
deliberately not this command's job. Report the contract digest, the objective's
current value, the drawn budget, and the next command in the cycle.
