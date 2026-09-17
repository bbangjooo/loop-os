# Loop OS — Make your dumb loop SMART

A three-layer system that takes a dumb hill-climbing loop and makes it smart:

- **Kernel** (`kernel/loop.py`) — a *dumb loop*. Measure, mutate once, run guards, commit or revert — one scalar objective, nothing else. The only thing that executes.
- **OS** (`os/`) — the *skills the dumb loop lacks*. Deterministic instruments for aiming, sealing evidence, steering, memory, autonomy grants, recovery, and jumping between hypothesis frames.
- **Application** (your repo) — the *problems that run on the OS*: quant research, ML tuning, refactoring — anything with a contract, an evaluator, and the journal.

The LLM proposes directions and interprets results, but its judgment enters the system only as digest-sealed files — if the file isn't there, the system structurally stops.

![Loop OS layers](docs/layers.png)

## Why

- **A dumb loop climbs one number — it can't ask whether the number is worth climbing.** The OS makes every objective cite the contract clause that licenses it as a proxy (`proxy_license`); the real verdict happens outside, on data the system can't read.
- **A dumb loop spends iterations — it can't police how many.** The OS turns budgets into multiple-testing contracts: iterations are drawn up front and never refunded, and abandoned runs still count.
- **A dumb loop reverts bad changes — it can't remember what happened.** The OS seals every run, diagnosis, and contract into a hash-chained journal, anchored in git so history can't be quietly rewritten.
- **A dumb loop can't change its own frame.** The OS owns jumps: a dead hypothesis class is replaced only through a reviewed, sealed adoption. Frames that preserve the contract's `[core]` constitution adopt autonomously; constitutional changes use a human signature by default or an explicit project-local full-auto config.
- **Any loop, any problem.** The kernel and OS know nothing about the domain — any repo with a contract and an evaluator runs unchanged, whether the problem is quant research, ML tuning, or refactoring.

## Getting Started

### Install

```bash
curl -fsSL https://raw.githubusercontent.com/bbangjooo/loop-os/main/install.sh | sh
```

This clones the repo into `~/loop-os`, installs dependencies with [uv](https://docs.astral.sh/uv/), installs the agent skill and slash commands into every harness it finds, and runs the test gate. Requirements: Python ≥ 3.11, git, uv, and an agent harness as the outer-loop runtime.

The examples below are Claude Code. Codex gets the same commands under flat names — `/loop-os-program`, `/loop-os-run-example`, `/loop-os-bootstrap`, `/loop-os-contract`, `/loop-os-cycle`, `/loop-os-status`.

The installer adds the Loop OS skill and slash commands to Claude Code or Codex. Run them from inside the project you want to work on.

### 0. Define the program

Before bootstrapping a project, run the bundled standalone deep interview:

```
/loop-os:program   # or: /loop-os:program <problem or research idea>
```

It works without GJC and writes a single `program.md` at the project root. The
program is the durable research plan: goal, research question, allowed
interventions, success evidence, falsifiers, constraints, non-goals, and the
human decision boundary. It does not edit application code or start execution.

The next step is:

```
/loop-os:bootstrap
```

`contract.toml` is derived from `program.md` and represents only the current
execution frame. The program remains stable while `jump` replaces frames.
New contracts bind its exact bytes with `[program]` (`path` and SHA-256 `digest`).
This is optional for compatibility with existing contracts, but the contract
builder includes it for new programs. See [program progress](docs/program-progress.md).

### 1. See it work

```
/loop-os:run-example
```

Runs the same kernel twice on the same 12-stop routing problem — once bare, once governed by the OS — in throwaway directories, no API key. Every step calls the real instruments:

![kernel (loop only) vs kernel + OS](examples/delivery-round/loop-vs-os.png)

- Same kernel, same objective (route length), same seeded proposals — the only difference is the OS around the loop.
- **Loop only** stalls at 403: its adjacent-swap frame is exhausted, and the kernel has no way to know — 75 of its 80 iterations are spent proposing into a dead frame.
- **With the OS**, three sealed runs (accepts 4 → 0 → 1) spend the generation's budget; the aim refusal, residual, dossier, independent review, and human approval license a **jump** to a 2-opt frame — and the same objective falls to 335.
- The kernel finds the best answer inside one frame. The OS decides which frame deserves the budget.

### 2. Bootstrap your own project

For a small recurring search comparison, see [Cafe queue](examples/cafe-queue/README.md).
It supplies a seeded scheduling task, automatic validity checks, a free FIFO demo
and a bounded two-session comparison of the added frame-exploration instructions.
The full Loop OS lifecycle remains demonstrated by the delivery-round example.

```
/loop-os:program   the test suite takes 40 minutes; I want it under 10 without losing coverage
/loop-os:bootstrap
```

- Your project is any git repository. Loop OS adds a **contract** (what to optimize, under which guards, with how much budget) and a **journal** (`.journal/` — hash-chained, gitignored, written only by instruments).
- Offers a per-frame git worktree when you'll run more than one frame — the kernel commits and reverts in the working tree, so frames sharing a checkout collide.
- Creates the journal, then feeds `program.md` to the **contract builder** (`/loop-os:contract`, also standalone): it turns the research plan into the four contract questions — objective, falsifiable mechanism, guards, budget — writes the evaluator if no command prints the number yet, and has the draft independently reviewed against a defect checklist before sealing. The contract is the one artifact nothing else in the system re-checks, so the review happens before the seal, not after.
- What comes out looks like the example's [gen1.toml](examples/delivery-round/contracts/gen1.toml).

Before selecting an initial or successor frame, the agent follows the
[frame exploration procedure](references/frame-exploration.md): baseline and
structural formulation, near/far search, analogy-first and method-first routes,
a recorded random cue, assumption inversion and failure inversion. It generates
before comparing, then records alternatives, transfer limits, falsifiers and a
smallest discriminating experiment. The existing `idea`/`rival_draft` notes carry
the comparison into independent review. This guides candidate generation; it does
not mechanically certify novelty or increase the experiment budget.

### 3. Run cycles

```
/loop-os:cycle       # one full cycle: aim → run → seal → diagnose → steer → anchor
/loop-os:status      # read-only: chain health, budget, next required action
```

`aim` is fail-closed. It refuses — with a code that names the missing input — when the journal is broken (`R1`), the contract drifted since registration (`R2`), a run is unsealed (`R3`), a diagnosis is missing (`R4`), or the generation budget can't cover the draw (`R5`). The refusal *is* the workflow: fix the named input and aim again, which is exactly what the cycle command does.

For program-bound runs, diagnoses also distinguish **outcome**, **learning**,
**preparation**, and **no_change** against a named program criterion. `steer
status` and `frame-health` expose the sealed declarations, unresolved work and
next action alongside the frame's numeric trajectory. More tests, collected
files or successful iterations can be useful preparation without producing the
result the user asked for. These reports do not certify completion; the
application's full success evidence still decides that.

### 4. Jump when the frame dies

A dead hypothesis class (three REJECTED diagnoses, or a spent budget) is replaced only through a **jump**: one atomic journal event citing the dossier, the successor contract, an independent review, and an approval — exactly what the example above did at iteration 30. The contract's constitution is its `[core]` table plus everything that defines the measurement — objective fields, guards, integrity pins, the per-generation budget. An **ordinary jump** preserves all of it and comes from a closed frame (spent budget or three REJECTED diagnoses); it adopts with auto approval, so frame exploration — new class, new mechanism, new prompts — needs no human in the loop. A **constitutional jump** changes one of those surfaces. Default mode waits for a human-authored approval; explicitly enabled full-auto mode seals the agent's structured decision and config digest instead. `/loop-os:jump` runs one full pass; the operating procedure is [SKILL.md](SKILL.md), and the design document is [docs/design.md](docs/design.md).

### 5. Run to the goal without approval stalls

Inject `autonomy.mode = "full_auto"` into the tracked `.loop-os/config.toml` when
you want to delegate constitutional decisions and journal recovery as well as
ordinary frame exploration. There is no separate full-auto skill or command: the
existing Loop OS skill reads the config, keeps independent jump review, archives
damaged journal bytes before recovery, and continues across cycles and generations
until the external goal's deterministic completion evidence passes. Default mode
is unchanged. Start the existing `$loop-os` skill in Codex Goal mode or use the
normal cycle command in either harness; the config changes its runtime behavior.
Disable the policy with `os/autonomy.py disable` to return to governed mode. See
[docs/full-auto-mode.md](docs/full-auto-mode.md) for recovery and rollback semantics.

## License

MIT

## Attribution

The bundled `skills/deep-interview/SKILL.md` is an adapted, standalone port of
GJC's `deep-interview` workflow from the Gajae Code project.

- Source: https://github.com/Yeachan-Heo/gajae-code
- Source revision: `0b2e1a15080b5d297a005c8e68b99e86ef7c9188` (2026-08-25)
- Original license: MIT
- Original copyright: Copyright (c) 2025-2026 Yeachan-Heo and Gajae Code Contributors
