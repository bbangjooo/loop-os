# Cafe queue: a small search experiment

**One barista, one machine, twelve customers. Reduce the time from ordering to
receiving a drink.** Each order needs preparation, automatic brewing and serving.
The machine can brew two compatible orders together; the barista can do one task
at a time. Orders cannot disappear, start before arrival, overlap on a resource,
or wait more than 12 simulated seconds between brewing and starting service.

The starting policy finishes each order before beginning the next. Agents can
change the scheduling algorithm in `policy.py`. Only the policy, task, training
orders and evaluator proxy are copied into an agent workspace; the scorer and
workload generator stay with the coordinator. Candidate code runs in a separate
Python process and returns only plans; the parent fixes durations and validates
every operation before scoring. The times are deliberately small
toy numbers, not measurements of a real cafe.

This problem offers several scheduling decisions without prescribing a winning
algorithm. It can connect to queues, manufacturing, pipelines and other domains.
An unfamiliar analogy alone earns no points: the resulting policy must work.

The [first accepted pilot](results/seed-1/README.md) records the measured scores,
costs, frozen policies and independent review, including limitations and rejected
calibration attempts. It found no solution-quality gain from the added guidance
on that single pair; future improvements can be compared without assuming a winner.

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

Requires a logged-in Claude Code CLI with MCP support. Omit `--model` to use its
isolated CLI default, or pass the same explicit model for both arms.

```sh
uv run python examples/cafe-queue/run.py pilot \
  --out /tmp/cafe-pair-s0 --seed 0 --eval-budget 12 \
  --usd-per-arm 2 --timeout 600 --effort low
```

Each arm gets a fresh workspace and session, the same eight training days,
starting code, evaluator, twelve evaluation calls, reasoning effort and reported
API cost ceiling. This reported cost is a resource measure, not subscription billing.
The CLI gets only the seven study MCP tools from `tools.py`: workspace file
access, syntax checking, counted evaluation and a random cue draw. It has no
shell, arbitrary code execution, web or subagent tool. File access cannot leave
the assigned workspace or rewrite protected inputs. Both arms get the same tools.
User/project settings, skills and non-managed hooks are disabled for the session;
the documented [memory environment switches](https://code.claude.com/docs/en/env-vars)
disable CLAUDE.md and auto memory. `--safe-mode` is not used because it also
disables the required MCP server. Actual available tools are verified in the
session's initialization record. Execution order is seeded. Model usage, cost,
duration, tool-event stream and evaluator records are retained.

- **Control:** the former mechanism-first pattern: formulate a falsifiable
  mechanism, implement, measure, interpret and revise.
- **Exploration:** the same task and control instructions plus the generation
  and comparison sections of `references/frame-exploration.md`, including a
  bounded candidate set, structural transfer, random cue and inversions.

This is an **ablation of the added search instructions**. It does not execute
the full Loop OS journal/kernel/jump lifecycle or compare two historical releases.
The explicit common task and treatment section are in each arm's `TASK.md`.
`manifest.json` records scenario seeds, source/reference hashes, CLI version and
requested model, reasoning effort, spending and time limits. Keep the original checkout available
for grading: comparison refuses if scorer sources changed after preparation.

Each `evaluate` tool call goes through the coordinator, evaluates the training
batch and costs one call, including invalid/interrupted attempts. Validity checks
and runtime profiling of candidates also use this tool; syntax checks are free.
The starting FIFO policy is evaluated once before either session and that charge
is included in each arm's budget. `baseline.json` exposes the common starting
score and remaining budget. The response includes evaluation duration.
Authoritative seeds, budgets, policy snapshots and logs live outside the agent
workspace. Workspace edits cannot reset them. The coordinator selects the valid
snapshot with the lowest training score (earliest trial wins ties), rather than
trusting the model's last edit. Both selected policies are copied into `frozen/`
before either holdout result is exposed; no fallback selection uses holdout scores.
The coordinator grades them with the original scorer on 64 other days (768 orders).
Coordinator grading is not feedback available during search and is outside the
training-call budget. Failed sessions, differing reported model sets, edited
scorers/configuration, invalid policies, missing/nonfinite/excess cost or duration,
and over-budget logs make a pair
ineligible for comparison.

Read `comparison.json` for mean, p95 and maximum receipt-to-service time,
training and holdout scores, candidate hashes, call counts, cost and automatic
eligibility. These checks do not certify session compliance: review the tool
trace and research artifacts independently before interpreting a result.
`provisional_holdout_delta_exploration_minus_control < 0` favors exploration. Inspect tail
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
creates the workspaces. Connect `python examples/cafe-queue/tools.py --workspace
<arm-dir>` as the sole MCP server and provide no general execution tools; give
each fresh session its `TASK.md`, then run `compare --out <dir>`. Without recorded
model/tool metadata the scores remain available but automatic eligibility is false.
The `objective.py` proxy is retained for human debugging; using it from an
unrestricted agent session is not the closed-tool experiment.

Use `--out examples/cafe-queue/runs/<unique-name>` to retain local experiments.
`runs/` is gitignored so full transcripts and temporary workspaces stay local.

## Limits

The repository source and workload generator are public, but are not supplied to
the agent workspace. The closed tool interface prevents ordinary file/shell
shortcuts; the Python policy worker is not a general hostile-code sandbox.
Retain the event stream and audit actual behavior before interpreting a result.
Final-state integrity checks do not prove that a file was never edited and
restored by another process. Holdout generalization discourages memorizing training days but is not
a proof of honesty or novel research. Both arms may already know scheduling
algorithms, and extra instructions can cost tokens without improving outcomes.

Policy imports are restricted to the deterministic modules listed in `TASK.md`.
Clock-based search limits are rejected: they can change the simulated result
with host load. Use fixed work limits instead. This source screen catches common
contract violations; it is not a general sandbox or proof of mathematical purity.
