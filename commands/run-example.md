---
description: Run the bundled Loop OS example — the same kernel bare vs governed by the OS — and explain the difference.
---

Run the bundled example and then explain what it shows. Nothing in the user's own
repository is touched.

```
sh __LOOP_OS_HOME__/examples/delivery-round/run.sh
```

The script runs the same kernel twice on the same 12-stop routing problem, in two
throwaway projects: once **loop only** (one frame, the whole budget, no
governance) and once **with the OS** (sealed runs, diagnoses, a budget refusal,
and a jump to a successor frame). The agent is a scripted stand-in — no API key.
If matplotlib is installed the run ends with `loop-vs-os.png` comparing both
paths; offer to open it.

Walk the user through the result in prose, using the real numbers from the
output:

1. **Both paths are the same kernel.** Same objective, same seeded proposals.
   The divergence is not a better optimizer — it is governance.
2. **Loop only stalls.** Quote its final objective and how many of its 80
   iterations were rejected. The kernel cannot know a move class is exhausted;
   it just keeps proposing.
3. **The OS turns the same stall into evidence.** Quote the three runs' accept
   counts and verdicts, then the `R5_BUDGET` refusal — the refusal is the
   workflow, not an error.
4. **The jump is licensed, not improvised.** Name the four files the adoption
   event cites (dossier, successor contract, independent review, human
   approval), and note the example scripts the last two only so it can run
   unattended — a real project must not.
5. **Generation 2 pays.** Quote the 2-opt run's descent and the final gap
   between the two paths.

Close with the one-line division of labor: the kernel finds the best answer
inside one frame; the OS decides which frame deserves the budget. Then point at
the bootstrap command for their own project. The example directories' path is
the last line of the output.
