---
description: Run a standalone deep interview and write the Loop OS program.md research plan.
---

Create the research program for the current project before Loop OS execution.
This is the standalone Loop OS adaptation of GJC's deep-interview workflow, so
it works even when GJC is not installed.

Read `__LOOP_OS_HOME__/skills/deep-interview/SKILL.md` and follow it exactly.
Let `$P` be the absolute path of the current project.

The interview is requirements-only. Do not edit product code, create a
contract, bootstrap the journal, run experiments, commit, or open a PR.

The output is `$P/program.md`. If `$P/program.md` already exists, read it and
ask whether to refine the existing program or start a new interview; do not
silently replace an existing research plan.

After the user confirms the one-sentence goal and the closure conditions, write
the final `program.md`. Then stop and tell the user to review it and run:

```text
/loop-os:bootstrap
```

Do not run bootstrap in the same interview pass.
