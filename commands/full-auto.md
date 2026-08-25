---
description: Run Loop OS continuously to the contract goal, including agent-decided constitutional jumps and journal recovery.
---

Operate the current project in **full-auto mode** until its contract goal is
achieved and verified. This command invocation is the user's explicit delegation
of constitutional-jump and journal-recovery decisions to the agent. Do not stop
at cycle or generation boundaries and do not wait for another human approval.

Loop OS lives at `__LOOP_OS_HOME__`; run every instrument by path from there. Let
`$P` be the absolute path of the current project. Read
`__LOOP_OS_HOME__/SKILL.md` completely before acting; its full-auto section governs.

## Enter full-auto

If `$P/.journal/` does not exist, bootstrap and seal a reviewed contract first.
Then record the opt-in grant:

```
uv run python os/autonomy.py enable --project $P \
  --approved-by "user invoking loop-os full-auto" \
  --statement "delegate constitutional jumps, journal recovery, and continuous goal execution to the agent"
```

When the journal is healthy, immediately run `os/journal.py anchor --project $P`
and commit `.loop-os-full-auto.json` with `.journal-anchor.json` before the first
aim; the kernel requires a clean tracked worktree. If enable reports
`PENDING_RECOVERY`, recover first and then make that commit. Do not weaken,
delete, or silently rewrite the grant. The rollback is explicit:
`os/autonomy.py disable --project $P --reason "..."`.

## Continuous program

Repeat this program without returning control merely because a pass completed:

1. Verify the journal and inspect status. Resume at `next_required`.
2. If verification fails, inspect the damaged bytes and anchor, author a recovery
   decision JSON with all fields below, run `os/autonomy.py recover`, inspect the
   recovered status, and continue. The recovery tool archives the original bytes.
3. Run the normal aim → kernel → run seal → diagnosis → frame-health → memory →
   anchor cycle. Resolve deterministic refusals as work items; they are not reasons
   to end the goal.
4. When the frame closes, perform a jump immediately. Use ordinary auto approval
   when its invariants fit. Otherwise make the constitutional decision yourself,
   obtain the required blind independent review, write a `full_auto` approval, and
   adopt it. Do not ask the user to approve it.
5. Register the successor, start its generation, and continue from step 1.
6. After every accepted change and generation transition, run the contract's
   objective and guards. Finish only when the target is met, all guards pass, no
   run or diagnosis is pending, the journal verifies, and the final head is anchored.

Recovery decision JSON:

```json
{
  "verdict": "RECOVER_AND_CONTINUE",
  "damage_assessment": "what broke and what remains readable",
  "evidence_considered": "journal bytes, anchor, git history, contract, ledgers",
  "continuation_rationale": "why the selected recovery is the strongest available continuation",
  "accepted_uncertainty": "what cannot be reconstructed or independently proven"
}
```

Constitutional full-auto approval JSON:

```json
{
  "mode": "full_auto",
  "decision": "why this constitutional change is necessary for the goal",
  "evidence": "the dossier, failures, measurements, and review supporting it",
  "goal_continuity": "why the successor still serves the user's original final outcome",
  "risk_assessment": "how the change can distort success or spend",
  "rollback_plan": "revoke before first draw, or the corrective successor afterward"
}
```

Keep the goal active through recoverable command errors, failed successor reviews,
contract drift, exhausted frames, and rejected hypotheses: diagnose, revise, or use
another evidence-preserving route. The mode still cannot perform actions outside
Loop OS vocabulary (deployment, release, capital allocation, live trading), and it
cannot override the agent host's sandbox or account limits. Within the permissions
already granted to the task, do not request interactive approval.
