# Cafe queue: a small search experiment

**One barista, one machine, twelve customers. Reduce the time from ordering to
receiving a drink.** Each order needs preparation, automatic brewing and serving.
The machine can brew two compatible orders together; the barista can do one task
at a time. Orders cannot disappear, start before arrival, overlap on a resource,
or wait more than 12 simulated seconds between brewing and starting service.

The starting policy finishes each order before beginning the next. Agents can
change the scheduling algorithm in `policy.py`. Candidate code runs in a separate
Python process and returns only plans; the parent fixes durations and validates
every operation before scoring. The times are deliberately small
toy numbers, not measurements of a real cafe.

This problem offers several scheduling decisions without prescribing a winning
algorithm. It can connect to queues, manufacturing, pipelines and other domains.
An unfamiliar analogy alone earns no points: the resulting policy must work.

## Quick check, without an LLM

From the Loop OS repository root:

```sh
uv run python examples/cafe-queue/run.py demo
uv run python -m pytest examples/cafe-queue/test_cafe.py -q
```

`demo` scores the supplied FIFO policy on eight seeded days. Tests cover a
hand-calculated scheduling improvement, invalid shortcuts, input mutation, the
evaluation limit, paired inputs, frozen outputs and model/scorer mismatch.
These tests run in CI and the installer gate; they make no model calls.

## One real A/B pair

Requires a configured Claude Code CLI supporting `--safe-mode`. Omit `--model`
to use its configured model, or pass the same explicit model for both arms.

```sh
uv run python examples/cafe-queue/run.py pilot \
  --out /tmp/cafe-pair-s0 --seed 0 --eval-budget 12 \
  --usd-per-arm 2 --timeout 600
```

Each arm gets a fresh workspace and session, the same eight training days,
starting code, evaluator, twelve evaluation calls and API spending ceiling.
Safe mode disables installed skills, hooks and memory so the control does not
automatically load the new Loop OS skill. Execution order is seeded. Actual model
usage, cost, duration, tool-event stream and evaluator records are retained.

- **Control:** the former mechanism-first pattern: formulate a falsifiable
  mechanism, implement, measure, interpret and revise.
- **Exploration:** the same task and control instructions plus the generation
  and comparison sections of `references/frame-exploration.md`, including a
  bounded candidate set, structural transfer, random cue and inversions.

This is an **ablation of the added search instructions**. It does not execute
the full Loop OS journal/kernel/jump lifecycle or compare two historical releases.
The explicit common task and treatment section are in each arm's `TASK.md`.
`manifest.json` records scenario seeds, source/reference hashes, CLI version and
requested model, spending and time limits. Keep the original checkout available
for grading: comparison refuses if scorer sources changed after preparation.

Every `objective.py` call evaluates the whole training batch and costs one call,
including invalid/interrupted attempts. The log survives git reverts. Both final
policies are copied into `frozen/` before either holdout result is exposed.
The coordinator grades them with the original scorer on 64 other days (768 orders).
Coordinator grading is not feedback available during search and is outside the
training-call budget. Failed sessions, differing reported model sets, edited
scorers/configuration, invalid policies, missing/nonfinite/excess cost or duration,
and over-budget logs make a pair
ineligible for comparison.

Read `comparison.json` for mean, p95 and maximum receipt-to-service time,
training and holdout scores, candidate hashes, call counts, cost and eligibility.
`holdout_delta_exploration_minus_control < 0` favors exploration. Inspect tail
latency as well as the mean. Do not call a policy better solely because it offers
more ideas or a more elaborate explanation.

## Reuse after an improvement

Use a fresh output directory for every pair; existing runs and frozen results
are never overwritten. Increasing `--seed` changes arrival times and menu mix.
Keep the same model and resource ceilings when comparing procedure versions.

```sh
uv run python examples/cafe-queue/run.py pilot --out /tmp/cafe-pair-s1 --seed 1
uv run python examples/cafe-queue/run.py pilot --out /tmp/cafe-pair-s2 --seed 2
```

Repeat both arms over several seeds **and** independent model runs. New problem
seeds vary the workload; repeated runs of the same seed also reveal model
sampling variability. One pair is a smoke-sized pilot. A tie, a loss or both arms
solving the task easily is an informative result, not grounds to redesign the
score after seeing outcomes. Preserve the starting problem and add a separately
versioned workload if it becomes too easy.

For another agent harness, `prepare --out <new-dir> --seed N --eval-budget 12`
creates the workspaces; supply each `TASK.md` to a fresh session, then run
`compare --out <dir>`. Without recorded model metadata the scores are available
but the runner does not mark the pair comparable.

## Limits

The source and workload generator are public; isolation is a protocol, not a
security sandbox. An agent that reads sibling files, performs unlogged scoring
or tampers with logs can violate it. Recorded evaluator calls are a lower bound
under such violations, so retain the event stream and inspect suspicious runs.
Final-state integrity checks do not prove that a file was never edited and
restored. Holdout generalization discourages memorizing training days but is not
a proof of honesty or novel research. Both arms may already know scheduling
algorithms, and extra instructions can cost tokens without improving outcomes.
