# Example — delivery round

A real optimization problem, small enough to read in a sitting: twelve stops, one
truck, and a route that crosses itself.

```bash
sh examples/delivery-round/run.sh [target-dir]
```

- `cities.json` — twelve fixed coordinates. Integrity-pinned: the agent may reorder
  the round, never move a city.
- `tour.json` — the order the driver currently uses. The agent edits only this.
- `objective.py` — total round-trip distance, printed as one number. Lower is better.
- `guard_tour_valid.py` — every city still visited exactly once. Without it, deleting
  stops would look like progress.
- `agent.py` — a scripted stand-in for the LLM: it reverses one randomly chosen
  segment (a 2-opt move) and has **no idea** whether that helps.

That last point is what makes this a real loop rather than a demo. The agent is not
an oracle; roughly half its proposals lengthen the round, and the kernel throws those
away with `git reset --hard`. The seed comes from `EXPERIMENT_LOOP_ITERATION`, which
the kernel hands the agent process — a rejected iteration is reverted, so without it
the next attempt would re-propose the same rejected move forever.

The script seeds a throwaway git repo (default: under `$TMPDIR`), then bootstraps the
journal, seals the contract, aims, commits the spec, runs the kernel, seals the run,
seals a diagnosis, and anchors the head. Every step calls the real instruments.

Expected result — deterministic, since the agent is seeded per iteration:

```
1 accepted  2015.947 -> 1893.706      5 rejected  1608.642 -> 1608.642
2 accepted  1893.706 -> 1891.481      6 rejected  1608.642 -> 1608.642
3 accepted  1891.481 -> 1608.642      7 accepted  1608.642 -> 1525.805
4 rejected  1608.642 -> 1646.536      8 rejected  1525.805 -> 1627.264
```

Four accepted, four reverted, 24% shorter — and the sealed denominator is 8, not 4,
because the budget counts what you tried, not what worked.

What this example is not: a real LLM agent, and a REJECTED verdict. Its mechanism is
close to true by construction — a real research contract never is, which is why the
diagnosis, the budget, and the journal exist at all.
