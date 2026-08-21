---
description: Bootstrap the current repository as a Loop OS application — create the journal, author contract.toml, and seal it.
---

Bootstrap the repository you are currently in as a Loop OS application.

Loop OS lives at `__LOOP_OS_HOME__`; every instrument is run by path from there
(`uv run python os/<instrument>.py`). Let `$P` be the absolute path of the current
project. Never write `.journal/` or a `spec.yaml` by hand — instruments own both.

Do this in order, stopping at the first thing you cannot determine on your own:

1. **Check the ground.** Confirm `$P` is a git repository with a clean-enough
   working tree, and check whether `$P/.journal/` already exists. If it does, this
   project is already bootstrapped — run
   `uv run python os/journal.py status --project $P` from `__LOOP_OS_HOME__`, report
   the `next_required` action, and stop.

2. **Learn the project before proposing anything.** Read the README, the test
   setup, and whatever script already measures quality. You are looking for four
   things: what a *better* result means here, one command that prints that as a
   single number, the commands that must keep passing (guards), and the files a
   change must never touch (integrity pins).

3. **Ask the user what you could not infer**, in one batch. At minimum: the real
   research goal behind the number, the falsifiable mechanism (why the objective
   can move at all), and the iteration budget for this generation. Do not invent a
   mechanism — an unfalsifiable `[frame] mechanism` is the single most common way a
   Loop OS project ends up measuring nothing.

4. **Offer to isolate the frame in its own worktree.** A generation climbs one
   hypothesis class, and the kernel commits and reverts inside the working tree, so
   two frames sharing one checkout will collide. If the user intends to run more than
   one frame, or wants the climb kept off their working branch, create a worktree for
   this frame and bootstrap *there* — `$P` becomes the worktree path for every step
   below:
   ```
   git -C <repo> worktree add ../<repo>-<frame> -b <frame>
   ```
   Use an orphan branch (`git switch --orphan`) only when the frame should not
   inherit the repo's history at all. Skip this whole step for a single-frame project
   — an unnecessary worktree is just another path to keep straight.

5. **Create the journal.**
   ```
   uv run python os/journal.py bootstrap --project $P --project-id <id>
   ```

6. **Author `$P/contract.toml`** using the schema in `__LOOP_OS_HOME__/README.md`.
   Requirements worth restating: `[stages.objective].command` must print one number
   on its last line; `proxy_license` must name the clause that licenses that number
   as a proxy for the real goal; `integrity` must pin the evaluator and any data
   surface a change could quietly rewrite; every guard must already pass on the
   current commit.

7. **Review the contract before sealing it — do not skip this.** Every iteration of
   the generation inherits whatever this file says, and once sealed the contract is
   integrity-pinned, so a flaw here is not something later cycles can notice. This is
   the one artifact in the system that nothing else checks: runs are sealed against
   it, diagnoses are judged against it, and the jump path reviews only its successor.

   Dispatch a subagent to review the draft against the checklist below. Give it the
   contract, the evaluator, and the guard commands, and ask for a defect list — not
   an opinion:

   - **Objective** — does the command actually print one number on its last line, on
     the current commit? Run it and confirm.
   - **Proxy** — does `proxy_license` name a real clause, or does it restate the
     objective in other words? "The number is the goal" is only honest when nothing
     outside the system decides the verdict.
   - **Mechanism** — is `[frame] mechanism` falsifiable? Ask what observation would
     refute it. If nothing would, it is a wish, not a mechanism.
   - **Guards** — do they all pass on the current commit, and does at least one of
     them fail when the objective is gamed the obvious way (deleting work, weakening
     a test, shrinking the input)? A guard set that cannot fail proves nothing.
   - **Integrity pins** — do they cover the evaluator *and* every data surface a
     change could quietly rewrite? An unpinned evaluator makes every later number
     unfalsifiable.
   - **Budget** — is `iterations_total` a number the user can defend as a
     multiple-testing contract, or a round number chosen for comfort?

   Fix what the review finds, then re-run the review if the contract changed
   materially. Report unresolved defects to the user rather than sealing over them.

8. **Seal it.**
   ```
   uv run python os/seal.py contract --project $P --contract $P/contract.toml
   ```

9. **Verify and report.** Run `uv run python os/journal.py status --project $P` and
   tell the user the sealed contract digest, the objective's current value, the
   drawn budget, and the exact next command in the cycle. If a guard fails or the
   objective command does not print a number, say so plainly and stop — a contract
   sealed over a broken evaluator poisons every iteration that follows.

The full operating procedure for the cycle after bootstrap is
`__LOOP_OS_HOME__/SKILL.md`.
