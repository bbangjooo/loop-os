# First accepted pilot — 2026-09-17

This is a single search-instruction A/B pair, not a full Loop OS lifecycle
benchmark or a general creativity result. Both sessions used reported model
`claude-opus-5[1m]`, effort `low`, a 12-evaluation ceiling including one initial
baseline, a $2 reported API-cost ceiling and a 600-second session limit.
Seed 1 generated eight training days and 64 separate final days (768 orders).
The seeded execution order was exploration, then control.

| Policy / instructions | Final mean wait | p95 | Maximum | Charged evaluations | Reported API cost | Session time |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Supplied sequential FIFO | 35.3971 s | 66 s | 89 s | — | — | — |
| Mechanism-first control | 13.6810 s | 28 s | 43 s | 8 | $1.509031 | 267.00 s |
| Added exploration guidance | 14.1042 s | 31 s | 43 s | 4 | $0.822704 | 177.39 s |

The exploration arm's mean was **0.423177 s (3.09%) higher**, with 45.48% less
reported API cost. These are different observed resource usages under the same
ceilings, not a comparison at identical actual spending. This pair does not show
a solution-quality gain from the added guidance; it also does not establish
general inferiority or explain the cause of the difference. Both improve on FIFO.
Costs in this table are CLI-reported values for this accepted pair, not a bill or
the total resource use of development/calibration attempts.

## Evidence

- [comparison.json](comparison.json) preserves the automatic report, scenario
  seeds, source/reference hashes, selected trial, actual model/usage and metrics.
  Its `protocol_review: REQUIRED` field is deliberately retained: automatic
  checks alone never certify session behavior.
- [review.md](review.md) records the separate independent review: **measurement
  integrity PASS**, snapshot selection/reported re-evaluation/numbers PASS.
- [control.py](control.py) is the selected trial 5, SHA-256
  `ad46dd03f08820ab70af46b3c85638386997929f640e77188eabe7c115624a0b`.
- [exploration.py](exploration.py) is the selected trial 4, SHA-256
  `535e45567b071225e8409686df0265433b115a487e7919214b2a6b0a307979ac`.

Exploration-method adherence was **PARTIAL**. Random cue extraction and the
candidate/comparison record preceded the first changed-policy evaluation, but
separate generation freezing, the method-first account and source-uncertainty
labels were incomplete. Treat the experiment as the effect of supplying the
guidance under this interface, not proof that every intended step was performed.
Research-note assertions about convergence or causality were not adopted as facts.

## Why earlier local attempts were discarded

Calibration exposed accidental evaluation routes: a policy shared a process with
its validator; later a model directly used the local validator for uncounted
debugging on seeds that overlapped the planned final set. Other runs used clock
deadlines or returned a policy other than the best observed one. Those attempts
were rejected rather than included as comparisons of method effectiveness.

The accepted protocol separates policy execution from validation, exposes only
bounded file/MCP operations, meters all candidate execution, screens clock/IO
imports, stores every evaluated source and selects the incumbent mechanically.
This pilot used fresh seed 1 after those protocol repairs; earlier observed
scores did not determine a new scoring function or a preferred winner.

## Repeat and inspect

From the repository root, repeat the matched setup on a new seed and new model
sessions:

```sh
uv run python examples/cafe-queue/run.py pilot \
  --out examples/cafe-queue/runs/seed-2 --seed 2 \
  --eval-budget 12 --usd-per-arm 2 --timeout 600 --effort low
```

To independently recompute the frozen policies' final scores without a model:

```python
import importlib.util
import json
from pathlib import Path

example = Path("examples/cafe-queue").resolve()
spec = importlib.util.spec_from_file_location("cafe_replay", example / "run.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
saved = example / "results/seed-1"
seeds = json.loads((saved / "comparison.json").read_text())["manifest"]["holdout_seeds"]
for arm in ("control", "exploration"):
    print(arm, runner.grade_frozen(saved / f"{arm}.py", seeds))
```

Use matching evaluator source hashes for exact historical replay. Repeating
several problem seeds and several model runs is needed before drawing a broader
conclusion. A further comparison with a lower shared evaluation ceiling would
help distinguish solution quality from the differing amounts of search used here.
