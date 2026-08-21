# Example — delivery round

The same kernel run twice on the same problem — once bare, once governed by the
OS. Fixed objective, fixed proposal seeds; the only difference is the OS.

```bash
sh examples/delivery-round/run.sh [target-dir]
```

`run.sh` calls nothing but `kernel/loop.py` and the `os/` instruments. Everything
else here is an artifact one of the three layers owns:

- **`app/`** — the application: `objective.py` (route length, cities pinned
  inside), `guard.py` (every stop visited once), two scripted agents
  (`agent_swap.py`, `agent_2opt.py` — stand-ins for the LLM, no API key), and
  `tour.json`, the one file the agents may edit.
- **`contracts/`** — three frames: `gen1.toml` (adjacent swap, budget 30),
  `gen2.toml` (2-opt successor), `loop-only.toml` (the same swap frame with the
  whole budget and no governance).
- **`judgments/`** — the files a real agent and human would author, pre-written
  with the numbers the deterministic runs actually produce: four diagnoses, the
  rival note, the independent review, the human approval. Pre-writing the review
  and approval is exactly what a real project must not do — they exist to force
  a second session and a human into the frame change.

What happens: **loop only** improves the round 540 → 403, exhausts its move
class, and spends the rest of 80 iterations proposing into a dead frame — the
kernel has no concept of "this strategy is done." **With the OS**, the same
frame runs as generation 1 in three sealed runs (accepts 4 → 0 → 1), the next
aim refuses with `R5_BUDGET`, and the jump path — residual → rival note →
dossier → review → approval → adopt — licenses a 2-opt generation that takes the
same objective from 403 to 335.

`plot.py` renders `loop-vs-os.png` from the runs' actual `summary.json` files
(needs matplotlib; skipped otherwise).
