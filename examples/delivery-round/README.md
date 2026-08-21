# Example — delivery round

The same kernel run twice on the same problem — once bare, once governed by the
OS. Fixed objective, fixed proposal seeds; the only difference is the OS.

```bash
sh examples/delivery-round/run.sh [target-dir]
```

The problem: find the shortest route through 12 delivery stops. The agent is a
scripted stand-in for the LLM (no API key needed), seeded per iteration from
`EXPERIMENT_LOOP_ID` and `EXPERIMENT_LOOP_ITERATION`, which the kernel sets for
the agent process.

**Loop only** (`seed/contract-loop-only.toml`): the adjacent-swap frame gets the
whole budget in one run. It improves the round from 540 to 403, exhausts its move
class, and spends the rest of its 80 iterations proposing into a dead frame — the
kernel has no concept of "this strategy is done."

**With the OS** (`seed/contract.toml`, then `seed/contract-gen2.toml`): the same
frame runs as generation 1 with a budget of 30, in three sealed runs (accepts
4 → 0 → 1, verdicts SUPPORTED / REJECTED / SUPPORTED). The next aim refuses with
`R5_BUDGET` — and that refusal is the workflow. The script then walks the real
jump path: `steer residual` → a `rival_draft` note → `steer dossier` → an
independent review file and a human approval file → `jump adopt` → the
generation-2 contract seals → a 2-opt frame takes the same objective from 403
to 335.

The review and approval files are scripted here so the example runs unattended.
That is exactly what a real project must not do — they exist to force a second
session and a human into the frame-change decision.

The chart (`loop-vs-os.png`, regenerated on every run if matplotlib is
installed) plots both paths' retained objective per iteration; `plot.py` reads
the actual `summary.json` files, not hardcoded numbers.

What this example is not: a real LLM agent, or a domain where the objective
could lie. Its objective *is* the goal (`proxy_license` says so) — in real
research the number is a proxy, and the contract review plus the sealed
denominator are what keep a good-looking number honest.
