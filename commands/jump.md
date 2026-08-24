---
description: Run one full Loop OS jump — rival draft, dossier, successor, blind review, approval tier, adopt, seal.
---

Run exactly **one** frame transition (jump) for the current project, then stop and
report. Do not chain a second jump on your own.

Loop OS lives at `__LOOP_OS_HOME__`; run every instrument by path from there. Let
`$P` be the absolute path of the current project. The full operating procedure is
`__LOOP_OS_HOME__/SKILL.md`; read its jump section before acting. It governs; this
command only sequences one pass through it.

Approval comes in two tiers, and the tier is decided by the contract text, not by
you:

- **Ordinary jump** — the successor carries the registered contract's `[core]`
  canonically unchanged, keeps `project.id` and `[revert]`, does not raise
  `budget.iterations_total`, keeps the set of stage objective measurement fields
  (command / direction / margin / target / proxy_license) exactly equal, carries
  every current guard on **every** stage, pins every current integrity path at
  top level, and the current frame is actually closed (three REJECTED diagnoses
  for the class, or the budget fully drawn with every run sealed-or-abandoned
  and diagnosed). You may author `approval.json` yourself as
  `{"mode": "auto", "basis": "core-preserved"}`. `os/jump.py` re-verifies every
  condition from the files and the journal; the ledger records
  `approval_mode = "auto"`.
- **Constitutional jump** — anything else: touching `[core]`, swapping or
  retuning an objective, shedding a guard or pin, changing `project.id`, raising
  the per-generation budget, or jumping from an open frame. Stop and ask the
  human for `approval.json {"approved_by": ..., "statement": ...}`. You never
  ghostwrite it.

If the registered contract has no `[core]` section, there is no auto tier at all:
every jump is constitutional until the human seals a constitution.

The pass:

1. **Legitimacy.** `uv run python os/journal.py status --project $P` and
   `uv run python os/steer.py frame-health --project $P`. A jump is warranted when
   the class is closed (three REJECTED diagnoses) or the generation budget is at
   its end. If neither holds, stop and report — a jump without a closed frame is
   frame-shopping, not research.
2. **Residual.** `uv run python os/steer.py residual --project $P` — the rejected
   mechanisms of the closing class. The rival must answer this list, not ignore it.
3. **Rival draft.** Author a `rival_draft` note (`os/note.py`) with
   commitment_rejected / proposed_frame / mechanism / falsifier. Prior binding: if
   any `external_evidence` notes exist, cite their ids in `--refs`.
4. **Dossier.** `uv run python os/steer.py dossier --project $P --rival <note_id>`,
   saved to a file.
5. **Successor contract.** Author it at its **own path** (e.g.
   `$P/contract.successor.toml`) — never overwrite the registered contract before
   adoption, or the auto tier loses its baseline and refuses. Set
   `frame.generation` = current + 1 and copy `[core]` from the registered contract
   **verbatim** unless the human has asked for a constitutional change. New class,
   new mechanism, new prompts, a different agent command are yours to design; the
   constitution — core, objectives' measurement fields, guards, pins — is not.
6. **Blind review.** Spawn a fresh subagent in a separate context — a different
   model route when one is available. Its inputs are exactly two file paths: the
   dossier and the successor contract. It must not see this conversation, the
   rival note's drafting history, or your reasoning. It writes `review.json`
   `{"reviewer": "<model/route>", "independent": true, "verdict": "PASS"|"FAIL",
   "notes": ...}`. On FAIL, fix the successor and re-run the review; never edit
   the verdict.
7. **Approval.** Decide the tier as above — author the auto file, or stop for the
   human. When in doubt, it is constitutional.
8. **Adopt.** `uv run python os/jump.py adopt --project $P --dossier D
   --successor S --review R --approval A`.
9. **Seal.** Copy the successor's bytes over `$P/contract.toml` (identical bytes,
   identical digest — the adoption still matches), then
   `uv run python os/seal.py contract --project $P`, then
   `uv run python os/journal.py anchor --project $P` and commit both.

Then report in a few sentences: the closed class and why it closed, the successor
class and mechanism, the review verdict, which approval tier applied, and the new
generation's budget. If you stopped at step 7 for a constitutional jump, say
exactly what in `[core]` the successor wants to change and wait.
