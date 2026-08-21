# Loop OS — Make your dumb loop SMART

A three-layer system that takes a dumb hill-climbing loop and makes it smart — without ever trusting the agent:

- **Kernel** (`kernel/loop.py`) — a *dumb loop*. Measure, mutate once, run guards, commit or revert — one scalar objective, nothing else. The only thing that executes.
- **OS** (`os/`) — the *skills the dumb loop lacks*. Seven deterministic instruments for aiming, sealing evidence, steering, memory, and jumping between hypothesis frames.
- **Application** (your repo) — the *problems that run on the OS*: quant research, ML tuning, refactoring — anything with a contract, an evaluator, and the journal.

The LLM proposes directions and interprets results, but its judgment enters the system only as digest-sealed files — if the file isn't there, the system structurally stops.

![Loop OS layers](docs/layers.png)

## Why

- **A dumb loop climbs one number — it can't ask whether the number is worth climbing.** The OS makes every objective cite the contract clause that licenses it as a proxy (`proxy_license`); the real verdict happens outside, on data the system can't read.
- **A dumb loop spends iterations — it can't police how many.** The OS turns budgets into multiple-testing contracts: iterations are drawn up front and never refunded, and abandoned runs still count.
- **A dumb loop reverts bad changes — it can't remember what happened.** The OS seals every run, diagnosis, and contract into a hash-chained journal, anchored in git so history can't be quietly rewritten.
- **A dumb loop can't change its own frame.** The OS owns jumps: a dead hypothesis class is replaced only through a reviewed, human-approved, sealed adoption.
- **Smart doesn't mean trusting the agent.** The loop is smart because the agent's judgment enters as digest-sealed, budgeted, reversible files — if the file isn't there, the system structurally stops.
- **Any loop, any problem.** The kernel and OS know nothing about the domain — any repo with a contract and an evaluator runs unchanged, whether the problem is quant research, ML tuning, or refactoring.

## Getting Started

### Install

```bash
curl -fsSL https://raw.githubusercontent.com/bbangjooo/loop-os/main/install.sh | sh
```

This clones the repo into `~/loop-os`, installs dependencies with [uv](https://docs.astral.sh/uv/), installs the agent skill into every harness it finds — Claude Code (`~/.claude/skills/loop-os`) and Codex (`~/.agents/skills/loop-os`) — and runs the test gate. Requirements: Python ≥ 3.11, git, uv, and an agent harness (Claude Code or Codex) as the outer-loop runtime.

There is no CLI product and no daemon. The instruments in `os/` are plain scripts, always run by path from this repo (the directory has no `__init__.py`, so it never shadows Python's stdlib `os` module).

### 1. Bootstrap and register

Your project is any git repository. Loop OS adds a **contract** (what to optimize, under which guards, with how much budget), a **journal** (`.journal/`, the only canonical record — hash-chained, gitignored, written only by instruments), and **specs** the kernel runs.

```bash
cd ~/loop-os
uv run python os/journal.py bootstrap --project ~/my-project --project-id my-project
# author contract.toml in your project (see below), then:
uv run python os/seal.py contract --project ~/my-project --contract ~/my-project/contract.toml
```

A minimal contract:

```toml
schema = "ros2-contract-v1"
integrity = ["evaluator.py"]              # pinned during runs; touching these voids the iteration

[project]
id = "my-project"

[frame]
generation = 1
class = "my_hypothesis_class"
mechanism = "why you believe the objective can move, in one falsifiable paragraph"

[budget]
iterations_total = 12                     # the generation's multiple-testing contract

[agent]
command = ["claude", "-p", "{prompt}", "--model", "claude-opus-5", "--dangerously-skip-permissions"]
timeout_seconds = 1800

[[stages]]
id = "main"
iterations = 8
prompt = "What the agent should attempt, one conceptual change per iteration."

[stages.objective]
command = ["python3", "evaluate.py"]      # prints one number on the last line
direction = "minimize"
margin = 1
target = 0
proxy_license = "which contract clause licenses this number as a proxy for the real goal"

[[stages.guards]]
id = "tests"
command = ["pytest", "-q"]
kind = "exit_zero"
```

### 2. Run the cycle

```bash
uv run python os/journal.py status --project ~/my-project   # tells you the next required input
uv run python os/aim.py --project ~/my-project --contract ~/my-project/contract.toml
cd ~/my-project && git add -A && git commit -m "spec"        # kernel refuses untracked specs
cd ~/loop-os && uv run python kernel/loop.py --repo ~/my-project run loop/runs/<date>-<loop_id>/spec.yaml
uv run python os/seal.py run --project ~/my-project \
  --summary ~/my-project/loop/runs/<...>/summary.json \
  --ledger  ~/my-project/.git/experiment-loop/<loop_id>/ledger.jsonl
# author diagnosis.json (verdict + what moved + mechanism + counterfactual + next question), then:
uv run python os/seal.py diagnosis --project ~/my-project --file diagnosis.json
uv run python os/journal.py anchor --project ~/my-project    # commit .journal-anchor.json
```

`aim` is fail-closed. It refuses — with a code that names the missing input — when the journal is broken (`R1`), the contract drifted since registration (`R2`), a run is unsealed (`R3`), a diagnosis is missing (`R4`), or the generation budget can't cover the draw (`R5`). The refusal *is* the workflow: fix the named input and aim again.

### 3. Read, remember, and jump

```bash
uv run python os/steer.py frame-health --project ~/my-project   # evidence + 3 interpretation requests, no verdicts
uv run python os/note.py --project ~/my-project --kind anomaly --body note.json --refs <event-id>
uv run python os/memory.py extract --project ~/my-project       # distill sealed diagnoses into claims
```

When a hypothesis class dies (three REJECTED diagnoses) or a generation's budget is spent, you change frames with a **jump** — the only path from advisory notes to a new contract:

```bash
uv run python os/steer.py residual --project ~/my-project             # what the rejections share
# author a rival_draft note, then:
uv run python os/steer.py dossier --project ~/my-project --rival <note-id> > dossier.json
# author the successor contract (generation + 1), an independent review, and a human approval file, then:
uv run python os/jump.py adopt --project ~/my-project \
  --dossier dossier.json --successor contract.toml --review review.json --approval approval.json
uv run python os/seal.py contract --project ~/my-project --contract ~/my-project/contract.toml
```

Adoption is one atomic journal event citing the four files' digests — no receipts, no phases. Registering a higher generation without that event is refused. Until the successor draws budget, an adoption can be undone (`os/jump.py revoke`), which also voids the registration that cited it.

The full operating procedure the agent follows is [SKILL.md](SKILL.md).

## Architecture

The design document is [docs/design.md](docs/design.md); the full architecture diagram lives at [docs/architecture-diagram.html](docs/architecture-diagram.html) (exported: [SVG](docs/architecture.svg) · [PNG](docs/architecture.png)).

![Loop OS architecture](docs/architecture.png)

- **Kernel — `kernel/loop.py`.** A single-file, stdlib+PyYAML, domain-free experiment loop, vendored byte-identical from its upstream (`infocz/gos`) and pinned by `kernel/VENDOR.json`. One inner-loop step: measure → agent mutates once → check pins → run guards → re-measure → commit or `git reset --hard`.
- **OS — `os/`.** Seven single-file instruments, each a pure function (files in → files out + at most one journal append): `journal`, `aim`, `seal`, `steer`, `note`, `memory`, `jump`. One outer-loop cycle: aim → run → seal → diagnose → steer → (jump) → aim.
- **Application — your repo.** A contract, an evaluator, data surfaces, and the journal. Two references exist: the toy project in `tests/` (runs in CI) and a live quantitative-research deployment.

### Integrity model

- The journal is append-only and hash-chained; every event cites its input files by SHA-256. Instruments are the only writers.
- The chain's one blind spot (a canonical edit to the newest line) is closed by **anchoring**: the verified head digest is committed to a git-tracked file, so rewriting sealed history breaks against git history.
- Anti-gaming is digests, budgets, and reverts — never permissions or trust. The contract itself is integrity-pinned during runs, so the frame cannot drift mid-climb.
- Deployment, releases, capital allocation, and live trading have no vocabulary here: no field in any schema could authorize them.

## Benchmark

The system's claims are measured, not assumed — see [bench/README.md](bench/README.md). The deterministic gate (red-team containment, capability floor, denominator honesty, crash resume) runs in CI on every push and PR to main. The measurement runner produces a scoreboard on synthetic problems with known ground truth, locally, with the scripted baseline or a real LLM agent:

```bash
uv run python bench/run.py --agent scripted
uv run python bench/run.py --agent claude --model claude-opus-5
```

What the benchmark cannot prove — real research efficacy on non-synthetic domains — is documented there honestly.

## License

MIT
