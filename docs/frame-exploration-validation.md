# Frame exploration validation

Verified on 2026-09-17 against base `d482c66`. This change adds an agent procedure
at initial contract selection and `residual → rival_draft`; the kernel, note
schemas, adoption rules and budget accounting are unchanged.

## Comparison with the requested methodology

| Method | Implemented behavior | Observed check |
| --- | --- | --- |
| 1. Existing solutions | Record baseline, bottleneck, uncertainty and inherited work | Initial tour 540.150; existing swap/reversal code treated as untested |
| 2. Abstraction | Concrete and structural formulations with preserved constraints | Closed cycle, visit permutation, symmetric edge costs and immutable evaluator separated from working assumptions |
| 3. Near/far search | Bounded candidate pass with room for both | Five candidates spanning local route edits, queue analogy, energy-barrier method and global reconstruction |
| 4. Structural similarity | Map variables/relations/constraints and name transfer failure | Queue-to-tour mapping records open-queue versus closed-cycle mismatch |
| 5. Analogy-first | Start from a situation, then extract shared structure | Factory queue led to a single-stop relocation candidate |
| 6. Method-first | Describe native method before fitting the problem | Energy-barrier escape considered, then rejected for incompatibility with the current acceptance policy |
| 7. Random exploration | Tool draw with explicit pool/seed/result; failed connections retained | Seed 2026091701 reproduced `error-correcting codes`; connection helped validity only and was not invented into a performance candidate |
| 8. Assumption inversion | Challenge working assumptions while preserving original requirements | Global order reconstruction challenged local repair; all visits and measurement definitions remained fixed |
| 9. Failure inversion | Derive an intervention and falsifier from a failure scenario | Poor boundary connections led to a bounded segment-reversal probe |
| 10. Generate/evaluate separately | Preserve candidate set, then compare fit, feasibility, novelty, outcome, learning and cost | Frozen generation file matched the compared candidates; zero candidate evaluations before independent contract review; literature novelty marked unknown |

The selected candidate was segment reversal, justified against relocation by the
available implementation and structural fit. This was a prediction, not an
advance claim of better performance. A second scenario with no feasible allowed
intervention and zero evaluation budget produced `candidate_id: null`, retained
the missing conditions and performed no experiment or adoption.

## Executed validation

- `uv run python -m pytest tests/ kernel/tests/ bench/ -q`: **222 passed, 1
  skipped** (Windows-only Job Object regression on macOS).
- Two new CLI integration tests in `tests/test_frame_exploration.py` exercise
  first-contract note/provenance and full successor comparison/prior handoff.
  They also verify that advisory candidates do not alter the executable prompt,
  generation, budget or adoption state.
- `sh -n install.sh` and skill-creator `quick_validate.py`: passed. The actual
  `install_skill` and `install_commands` functions were executed with temporary
  destinations: the relative skill reference was copied and command paths were
  expanded to the checkout. No account home override was used.
- An independent code reviewer returned PASS after examining the changed files
  and existing note/dossier/contract/approval consumers.
- A separate agent followed the procedure on the supplied delivery application,
  sealed an `idea`, and prepared a contract. An independent reviewer then loaded
  the verified note, reproduced the random draw, checked the candidate digest,
  source uncertainty, selection/contract match and 12/4 iteration limits: PASS.
- The reviewed contract was sealed and its first spec executed with the real
  kernel. First proposal: 540.150 → 541.808, rejected and reverted. Second:
  540.150 → 458.893, accepted with guards passing. The checkpoint stopped the run
  after **2 actual iterations**, while the original **4-iteration draw** remained
  charged out of the 12-iteration generation. Run and diagnosis were sealed;
  journal verified and anchored with no pending run or diagnosis.

The first kernel launch correctly refused the fixture's default `main` branch.
Switching to a dedicated loop branch resumed the same pending spec without a new
draw. The exploration handoff now explicitly includes that prerequisite and
recovery instruction.

## What these checks establish

The authoring procedure was followed in one realistic positive scenario and one
no-candidate scenario; the existing artifact and execution paths carried the
results through review and sealing. Candidate comparison is finalized advisory
data for reviewers, not private drafting history. The instruments do not certify
that its reasoning or claimed source content is true.

This is not an efficacy comparison against the previous Loop OS. The delivery
case uses a bundled proposer; an example result was accidentally exposed during
the author's schema search and disclosed, so the test was not fully blinded.
The generation digest verifies preserved contents, not the author's mental order.
Two logged candidate trials are not an independently instrumented count of every
raw evaluator subprocess call. Neither creativity uplift, literature novelty,
global route optimality nor real-road savings is established.

An efficacy study would hold model, task set, generation cost and evaluation
budget constant, compare the old procedure with this procedure across repeated
runs, and assess final task outcomes, cost and repeated failures. That study is
separate from this feature's integration and behavioral validation.
