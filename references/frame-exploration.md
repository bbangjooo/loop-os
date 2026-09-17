# Frame exploration

Use this procedure before selecting the first contract's frame and between
`residual` and `rival_draft` when selecting a successor. Also use it before
promoting a frame-health suggestion into a rival. Read the program, current
contract if any, verified notes, and relevant diagnoses first. Finish pending
runs and diagnoses before adopting a successor; brainstorming grants no execution
authority. Ordinary cycle iterations do not repeat this whole procedure.

The output is a bounded, compared set of mechanisms and one justified selection.
This is an agent authoring/review procedure. Instruments seal its bytes; they do
not certify creativity, source truth, structural similarity, or search coverage.

## Generate before comparing

1. **Baseline.** Identify existing approaches, their observed results and the
   remaining bottleneck. Cite evidence, distinguish observations from assumptions,
   and retain the disposition of inherited candidates and required follow-ups.
   If a baseline has not been measured, mark it unknown and plan its measurement.
2. **Abstraction.** Write both the concrete problem and a structural version:
   variables, relationships, objective and constraints. Keep enough detail to
   distinguish this problem from generic optimization. Separate user requirements
   and validity conditions from working assumptions that may be challenged.
3. **Near and far search.** Set a small candidate limit and one generation pass
   before searching; 4–6 candidates is a useful starting point, not a quota.
   Reserve room for both nearby techniques and a distant field. Track generation
   effort separately from the existing experiment/evaluator budget. Do not score
   feasibility or rank candidates until the generation pass is recorded.
4. **Structural transfer.** For a distant candidate, map source variables,
   relations and constraints to the target. State a concrete condition under
   which the transfer breaks. A new domain name or a metaphor is insufficient.
5. **Analogy-first.** Start with a situation or example before deriving its shared
   structure. Retain what the comparison reveals or where it fails.
6. **Method-first.** Select a method from another field before fitting it to the
   current formulation. Describe its native purpose first to reduce anchoring.
   These are alternative routes; do not force every candidate through both.
7. **Random cue.** Sample one cue from an explicit pool of different fields or
   methods using a tool (for example a seeded standard-library random draw).
   Record the pool, seed/draw method and result. Attempt a structural connection;
   a failed connection is a valid result. Do not relabel a preferred candidate as
   random or claim the model's choice was an independent random draw.
8. **Assumption inversion.** Challenge a working assumption and propose how the
   original outcome could still be achieved without it. Preserve user constraints
   and validity conditions. Changes to goals, measurements, guards or budgets use
   the existing constitutional approval path; creativity is not authorization.
9. **Failure inversion.** Ask what would make the original outcome fail, then
   derive an intervention and an observable falsifier. This changes the route to
   success, not the definition of success.

Record which routes produced each candidate. A candidate may serve several
routes. Keep unsuccessful attempts as such rather than inventing extra candidates
to meet a count. For a narrowly prescribed intervention, scale down the pass and
explain any omitted route; do not manufacture permission to change the task.
Label remembered or invented examples as unverified. Source verification can
follow generation, but an unverified analogy must not become an established prior.

## Compare, then select

10. **Evaluation.** Freeze the generated candidate list in the record, then
    compare it. Merge candidates with the same mechanism even if their vocabulary
    differs. Compare feasibility, structural fit, novelty relative to the
    baseline, expected outcome, learning value and cost. Mark performance as a
    prediction unless measured; mark literature novelty unknown unless checked.
    Reject a transfer whose required conditions contradict known evidence.

Choose one candidate with a smallest discriminating experiment: intervention,
observation, competing predicted outcomes/falsifier and estimated evaluation
cost. Explain why it beats the strongest alternative, how inherited obligations
are handled, and what evidence would reopen a rejected/deferred candidate.
If none is usable, record that result and the missing evidence or reformulation;
do not invent a winner to unlock adoption. At most one additional generation pass
may target a named gap within the recorded limit; otherwise report the unresolved
gap or follow the project's authorized continuation policy.

Comparing proposals here is a desk review, not an unlogged experiment. Execute
candidate or baseline performance measurements only through the contract/evaluator
workflow and its budget. Initial evaluator construction/current-state validation
uses the contract builder's existing checks; do not test a portfolio during setup.
Do not read held-out answers or recompute the objective outside the instrument.
After a run, feed the diagnosis into the next exploration: distinguish a failed
implementation, failed transfer assumption and failed mechanism. Record learning
as learning, and outcome changes against the program's success evidence.

## Record and hand off

Author a JSON object with these fields. They describe an advisory artifact, not a
new contract or note schema. Keep explanations concise and concrete.

| Field | Contents |
| --- | --- |
| `baseline` | Existing approaches, evidence/unknowns, bottleneck and inherited-work disposition |
| `abstraction` | Concrete and structural formulations; preserved constraints and challengeable assumptions |
| `search` | Candidate/pass limits, effort used, route attempts including unsuccessful/omitted routes, random pool/draw/result |
| `candidates` | Each candidate's `id`, `routes`, `source` and verification status, `mechanism`, `structural_mapping`, `transfer_break`, `falsifier`, `minimal_experiment` |
| `comparison` | Per-candidate decision and reasons: feasibility, fit, novelty/unknowns, predicted outcome, learning value, cost; duplicates and evidence refs |
| `selection` | Candidate id (or null), reason versus the strongest alternative, inherited-work disposition and evidence that would change the choice |

Use the existing note lane and keep the entire finalized comparison available to
the reviewer. Do not put private drafting history or a conversation transcript in
the artifact. The candidate record is a reviewable research result.

- **First contract:** before a journal exists, save only a draft JSON outside
  `.journal/`. Once bootstrapped, seal it as an `idea` via `os/note.py --kind idea
  --body <file>`. Pass the verified note body and returned note id to the contract
  reviewer along with the draft contract, evaluator and guards. Add a TOML comment
  `# exploration: <note-id>; selected: <candidate-id>` to the contract before
  sealing; its digest binds that provenance without adding a contract field.
  Align the actual mechanism and first stage with the selected experiment.
- **Successor:** put the full finalized object in the rival body's `exploration`
  field, alongside `commitment_rejected`, `proposed_frame`, `mechanism` and
  `falsifier`. Cite relevant run/note evidence in `--refs`. Verified external
  sources use `external_evidence` notes with their existing required fields;
  cite those note ids directly in the rival's `--refs` for prior binding and
  inclusion in the dossier. An `idea` id alone does not satisfy prior binding.
  `steer dossier` already includes the entire rival body, so the blind reviewer
  receives all alternatives, comparison and selection in its existing two inputs.

Use `note.load_notes` to retrieve digest-verified notes for review; an editable
draft or an unchecked line in `notes.jsonl` is not the sealed record. Missing or
tampered records must be recovered/re-authored and sealed through the existing
instruments. Keep contract and note provenance consistent when revising a choice.
Before the next kernel execution, use a dedicated loop branch permitted by the
kernel, commit authoring files and anchor the journal. If a protected-branch
refusal occurs after `aim`, switch branches and resume the already issued spec;
do not issue another spec or redraw the budget.
Do not modify a registered contract in place to add a record retroactively.

The independent reviewer checks the baseline, actual mechanism diversity,
structural correspondences and break conditions, source uncertainty, failure
inversion, budget, selection versus alternatives, and contract/selection match.
It returns concrete defects for missing or contradictory evidence, including
goal weakening presented as assumption inversion. The original contract and jump
review/approval requirements still apply. On failure, revise the comparison and
affected contract, seal a new note, rebuild the dossier if applicable and re-review.
Never edit a sealed note or the reviewer's verdict.
