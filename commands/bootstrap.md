---
description: Bootstrap the current repository as a Loop OS application — create the journal, then build and seal the contract.
---

Bootstrap the repository you are currently in as a Loop OS application.

If the user passed anything after the command, treat it as the plain-language
problem statement — what they want to get better — and carry it into step 4 so the
contract builder starts from it instead of asking again.

Loop OS lives at `__LOOP_OS_HOME__`; every instrument is run by path from there
(`uv run python os/<instrument>.py`). Let `$P` be the absolute path of the current
project. Never write `.journal/` or a `spec.yaml` by hand — instruments own both.

Do this in order, stopping at the first thing you cannot determine on your own:

1. **Check the ground.** Confirm `$P` is a git repository with a clean-enough
   working tree. If `$P/.journal/` already exists, the project is bootstrapped — run
   `uv run python os/journal.py status --project $P`, report `next_required`, stop.

2. **Offer a per-frame worktree.** The kernel commits and reverts inside the working
   tree, so two frames sharing one checkout collide. If the user will run more than
   one frame, or wants the climb off their working branch, create a worktree and
   make it `$P` for every step below:
   ```
   git -C <repo> worktree add ../<repo>-<frame> -b <frame>
   ```
   Use an orphan branch only when the frame should not inherit history. Single-frame
   project: skip this step.

3. **Create the journal.**
   ```
   uv run python os/journal.py bootstrap --project $P --project-id <id>
   ```

4. **Build and seal the contract** by following
   `__LOOP_OS_HOME__/commands/contract.md` — the contract-builder command, also
   available directly as its own slash command. Hand it the problem statement from
   the command argument if one was given. It interviews the user from that
   statement, builds the evaluator if none exists, drafts `contract.toml`, has the
   draft independently reviewed against a defect checklist, and seals it. Do not
   seal an unreviewed contract.

5. **Verify and report.** Run `uv run python os/journal.py status --project $P` and
   tell the user the sealed contract digest, the objective's current value, the
   drawn budget, and the exact next command in the cycle. If a guard fails or the
   objective command does not print a number, say so plainly and stop — a contract
   sealed over a broken evaluator poisons every iteration that follows.

The full operating procedure for the cycle after bootstrap is
`__LOOP_OS_HOME__/SKILL.md`.
