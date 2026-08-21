---
description: Run the bundled Loop OS example end to end and explain what each sealed event proves.
---

Run the bundled example — one complete outer-loop cycle on a throwaway project —
and then explain the result. Nothing in the user's own repository is touched.

```
sh __LOOP_OS_HOME__/examples/delivery-round/run.sh
```

The script seeds a small git repo holding a real optimization problem — twelve
delivery stops and a route that crosses itself — then bootstraps the journal, seals
the contract, aims, runs the kernel, seals the run, seals a diagnosis, and anchors
the head. Every step calls the real instruments; the only thing faked is the agent,
and the kernel cannot tell the difference — it never trusts the agent anyway.

The scripted agent proposes a random 2-opt move and is not an oracle: about half its
proposals lengthen the round and get reverted. Expect roughly four accepted and four
rejected iterations.

Run it, then walk the user through what actually happened, in prose, using the real
numbers from the output:

1. **aim drew budget.** Quote `draw` and `budget_remaining` from `SPEC_ISSUED`, and
   say plainly that the draw is spent whether or not the run succeeds — that is what
   makes the budget a multiple-testing contract rather than a quota.
2. **The kernel climbed — and threw work away.** Quote the objective's before/after
   and the per-iteration decisions from `summary.json`, including the rejected ones.
   The rejections are the interesting part: the agent proposed them in good faith,
   the objective disagreed, and `git reset --hard` erased them. Note that the guard
   ran on every iteration, and that a guard failure would have reverted the commit
   even if the number had improved.
3. **The run and the diagnosis were sealed.** Quote `trials_denominator` and the
   verdict, and note that the denominator counts evaluations, not successes.
4. **The head was anchored.** Quote the anchor `head` and explain that committing
   `.journal-anchor.json` is what closes the chain's tail-edit blind spot.
5. **Where it stands now.** Quote `next_required` from the final status.

Then say what this example deliberately does *not* show: a real LLM agent, a real
research question, and a REJECTED verdict. The example's mechanism is true by
construction, which is exactly the situation a real contract never enjoys.

Finish by pointing the user at the bootstrap command to set up their own project.
The example directory is left on disk; its path is the last line of the output.
