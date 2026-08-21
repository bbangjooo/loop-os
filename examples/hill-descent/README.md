# Example — hill descent

One complete outer-loop cycle, small enough to read in a sitting.

```bash
sh examples/hill-descent/run.sh [target-dir]
```

`value.txt` holds a number and the objective prints it; smaller is better. `agent.py`
is a scripted stand-in for the LLM — it lowers the number by exactly one — so the run
is deterministic and needs no API key. The kernel cannot tell the difference, which
is the point: it never trusts the agent either way.

The script seeds a throwaway git repo (default: under `$TMPDIR`), then bootstraps the
journal, seals the contract, aims, commits the spec, runs the kernel, seals the run,
seals a diagnosis, and anchors the head. Every step calls the real instruments.

Expected result: the objective falls 10 → 7 over three accepted iterations, the
`app-intact` guard passes on each, and the generation has 3 of its 6 iterations left.

What this example is not: a real agent, a real research question, or a REJECTED
verdict. Its mechanism is true by construction — a real contract never is, which is
why the diagnosis, the budget, and the journal exist at all.
