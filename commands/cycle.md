---
description: Run one full Loop OS outer-loop cycle — aim, run the kernel, seal, diagnose, steer, anchor.
---

Run exactly **one** outer-loop cycle for the current project, then stop and report.
Do not start a second cycle on your own.

Loop OS lives at `__LOOP_OS_HOME__`; run every instrument by path from there. Let
`$P` be the absolute path of the current project, and `$C` its contract file.

The full operating procedure — absolute rules, refusal-code table, diagnosis file
format, note kinds — is `__LOOP_OS_HOME__/SKILL.md`. Read it before acting. It
governs; this command only sequences one pass through it.

The pass:

1. `uv run python os/journal.py verify --project $P` — chain + anchor. If it fails,
   stop and report to the user; a broken chain is an evidence incident, not a
   problem to route around.
2. `uv run python os/journal.py status --project $P` — `next_required` tells you
   where in the cycle this project actually is. Resume there rather than assuming
   step 3.
3. `uv run python os/aim.py --project $P --contract $C` — emits the spec. On a
   refusal, follow the refusal-code table in SKILL.md: the refusal names the missing
   input, and supplying it *is* the work. Never hand-write a spec.
4. Commit the spec in `$P` — the kernel refuses an untracked in-worktree spec.
5. `uv run python kernel/loop.py --repo $P run <spec_path>` — this is the only step
   that executes anything.
6. `uv run python os/seal.py run --project $P --summary <summary.json> --ledger
   $P/.git/experiment-loop/<loop_id>/ledger.jsonl` — if the run declared
   `offline_evals=N`, seal with `--declared-evals N`.
7. Author the diagnosis file in the SKILL.md format — verdict, what moved, mechanism,
   counterfactual, next question — then
   `uv run python os/seal.py diagnosis --project $P --file <diagnosis.json>`.
   Write what the evidence supports, including REJECTED. A generation that never
   rejects is a generation that never measured anything.
8. `uv run python os/steer.py frame-health --project $P` — answer all three
   interpretation requests, recording each `yes` as the note kind it names.
9. `uv run python os/memory.py extract --project $P`.
10. `uv run python os/journal.py anchor --project $P`, then commit
    `.journal-anchor.json`.

Then report to the user in a few sentences: the verdict, the objective before and
after, iterations drawn and left in the generation, and the next required action.
If the generation's budget is now spent or the hypothesis class has three REJECTED
diagnoses, say so — the next move is a jump, which is a separate, human-approved
decision you do not make on your own.
