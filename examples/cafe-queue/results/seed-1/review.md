# Closed-tool seed1 final independent audit

**Measurement integrity: PASS for both arms.**
**Exploration treatment adherence: PARTIAL.**
**Snapshot selection and recorded comparison consistency: PASS.**

This is one paired instruction-ablation pilot. These verdicts do not establish general effectiveness of the exploration method or a causal mechanism. The original ten-step procedure was not executed perfectly, and this is not a full Loop OS kernel/journal version comparison.

## Control trace and execution boundary

The control initialization lists exactly the seven cafe MCP tools and one connected cafe server; main model is claude-opus-5[1m]. Every observed call is a cafe RPC. Counts:7 read_file,1 list_files,3 write_file,21 edit_file,7 syntax_check,7 evaluate. Reads are assigned-workspace task/baseline/orders/config/proxy/policy files. Writes are policy.py, research.json and one scratch/ backup. No native shell, external code execution, outside-path read/write, sibling/source lookup, web/skill/subagent or holdout access is observed.

The seven evaluate calls are stream68,84,121,150,159,172,186. Along with the pre-session charged FIFO baseline they exactly match8 coordinator trial/result records. Syntax checks report executed:false. Candidate code uses simulated event time and fixed MAX_SIMS/MAX_PASSES limits, not a host clock. Its internal event simulator and configuration search are allowed policy logic. The selected and final policies contain no imports, file/process inspection, reflection or dynamic execution. Local simulated time is not a clock violation.

The exploration trace was independently reviewed in `/tmp/loop-os-cafe-exploration-review-closed.md`: exactly seven cafe tools available; all calls within that set; three candidate evaluations plus one charged baseline; no measured boundary violation. This final audit retains that PASS.

## Resource and outcome records

Manifest: schema cafe-search-ablation-v3, master seed1,8 shared training days,64 disjoint shared holdout days,12 evaluation allowance per arm (baseline included), low effort,$2 reported API-cost ceiling,600 seconds, Claude CLI2.1.245. Both sessions report only claude-opus-5[1m] in modelUsage, success, study_tools_verified:true, no protected-file changes and cost/time within limits.

| Record | Control | Exploration |
| --- | ---: | ---: |
|Model evaluate calls|7|3|
|Total charged evaluations incl. baseline|8|4|
|Reported API cost USD|1.509031|0.8227035|
|Session wall seconds|267.001273|177.389724|
|Selected coordinator trial|5|4|
|Selected training mean wait|13.8854166667|14.2395833333|
|Holdout mean wait|13.6809895833|14.1041666667|
|Holdout p95|28|31|
|Holdout maximum|43|43|
|Holdout order count|768|768|

Shared measured training baseline is35.1354166667. Recorded FIFO holdout mean is35.3971354167. Both selected policies are valid on their recorded training and holdout results.

Arithmetic difference: **14.1041666667 −13.6809895833 = +0.4231770833 simulated seconds/order**. This matches comparison.json. In this recorded pair the selected exploration policy has the larger mean wait and consumed fewer calls, less reported cost and less wall time. Do not attribute those differences to a specific mechanism, generalize the sign to future runs, or present the result as proof of either method's superiority. The study matched resource allowances, not actual consumed calls/tokens/time.

## Selection, bytes and recorded re-evaluation

All evaluated policy snapshots in both arms match the corresponding result SHA-256. Protected workspace files match manifest hashes. The train/holdout day-seed sequences in comparison.json match their respective manifest splits and do not overlap.

Control trials5–8 tie at13.8854166667, so the earliest-tie rule correctly selects trial5:
`ad46dd03f08820ab70af46b3c85638386997929f640e77188eabe7c115624a0b`.
Its frozen bytes match the measured snapshot. The model's final trial8 file differs only by one blank line; the coordinator's choice is nevertheless correctly based on trial5, not on the final edit.

Exploration trial4 is the unique lowest valid recorded mean at14.2395833333:
`535e45567b071225e8409686df0265433b115a487e7919214b2a6b0a307979ac`.
Its frozen bytes match the measured snapshot and current model file.

For both arms, the coordinator's stored training re-evaluation agrees with the selected result **for every per-day mean**, not merely the aggregate. Holdout aggregate means also agree with the arithmetic average of the recorded64 per-day means. These are checks of stored outputs; this reviewer did not rerun a scorer or candidate. Selection uses training evidence only, and the source path reviewed earlier freezes both training-selected policies before holdout grading. No model trace exposes holdout feedback.

`automatic_checks_passed:true` is supported. comparison.json still says `protocol_review:REQUIRED`; this document supplies the independent **measurement-integrity PASS** while retaining the separate treatment qualification.

## Treatment adherence qualification

The exploration trace now provides the key ordering evidence: random_cue at56/57, candidate/structural/falsifier/desk-comparison file write at62/63, policy write65, first changed-policy evaluation69. Five candidates and a hospital-OR reservation mapping, a transfer break condition, an assumption inversion and a failure inversion were present before testing. Later evidence was added afterward. This is substantial procedural use, unlike earlier retrospective-only attempts.

PARTIAL remains appropriate because generation and desk comparison are written together, not independently frozen in separate observable phases; method-first/native-purpose documentation is weak; source uncertainty for the medical analogy is not explicit; strongest-alternative/per-candidate comparisons and literature-novelty uncertainty are incomplete. Combining several mechanisms in the first implementation also prevents separating their causal contributions. Details remain in the earlier exploration audit. Artifact shortcomings are not being reclassified as unlogged scoring or holdout leakage.

## Narrative corrections for publication

- Both model notes incorrectly call the objective serve-start wait. The evaluator measures serve completion. For a fixed valid day's plans the two totals differ by the constant sum of service durations, so the primary ranking/minimizer is exactly equivalent; the coordinator's reported metrics are authoritative.
- Control research omits coordinator trial4 (valid14.0208333) from its narrative list; the authoritative8-record ledger remains complete. A published trial table should use the ledger rather than claiming the notes cover every trial.
- Control's early “~80x runtime headroom” compares an8-day timing against a64-day limit; simple8× extrapolation gives about11x, not80x. The later best-policy runtime projection is roughly2.6seconds/64 days and still only a projection.
- “Dominant mechanism confirmed”, convergence/local-optimum assertions based on repeated score ties, and approximate unseen-day ranges are hypotheses, not demonstrated conclusions. Preserve these as model-authored interpretations rather than adopting them as evaluator findings.

## Scope

Read-only inspection of the requested control files/tool trace, both evaluation ledgers/results/snapshots, frozen outputs and comparison.json, with the prior independent exploration review retained. Only hashes and arithmetic over already stored results were calculated. No new model call, policy evaluation, holdout evaluation or source modification occurred. Earlier protocol-failed pilots remain failed and should be retained separately; this PASS applies only to this closed-tool seed1 pair.
