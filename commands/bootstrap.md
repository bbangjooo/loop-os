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

4. **Create the journal.**
   ```
   uv run python os/journal.py bootstrap --project $P --project-id <id>
   ```

5. **Author `$P/contract.toml`** using the schema in `__LOOP_OS_HOME__/README.md`.
   Requirements worth restating: `[stages.objective].command` must print one number
   on its last line; `proxy_license` must name the clause that licenses that number
   as a proxy for the real goal; `integrity` must pin the evaluator and any data
   surface a change could quietly rewrite; every guard must already pass on the
   current commit.

6. **Seal it.**
   ```
   uv run python os/seal.py contract --project $P --contract $P/contract.toml
   ```

7. **Verify and report.** Run `uv run python os/journal.py status --project $P` and
   tell the user the sealed contract digest, the objective's current value, the
   drawn budget, and the exact next command in the cycle. If a guard fails or the
   objective command does not print a number, say so plainly and stop — a contract
   sealed over a broken evaluator poisons every iteration that follows.

The full operating procedure for the cycle after bootstrap is
`__LOOP_OS_HOME__/SKILL.md`.
