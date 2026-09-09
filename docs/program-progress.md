# Program identity and progress

A frame can improve its scalar while the intended application outcome stays
unchanged. A long sequence of data repairs, code reviews and successful checks
may prepare an experiment without producing a usable result. Loop OS keeps
those distinctions visible without pretending to judge their meaning.

## Bind the durable program

New contracts may include this optional table:

```toml
[program]
path = "program.md"
digest = "<64 lowercase hexadecimal characters: SHA-256 of the exact file bytes>"
```

The path must resolve to a file inside the application project. Compute the
digest from the reviewed file, then include the table when authoring the
contract. `seal contract` checks it before registration. `aim` checks it before
reserving another draw, adds the file to integrity and emits an ordinary
`exit_zero` digest guard in every kernel stage. The guard also catches a program
edited and committed after spec issuance, before kernel entry. The reserved
guard id is `loop-os-program-digest`.

Changing or dropping `[program]` makes a jump constitutional. The existing
human/full-auto approval paths apply; no new permission system is introduced.
Program changes should use a new file/version, preserving the old bytes while
issued runs and diagnoses still reference them. Re-sealing the same unchanged
contract cannot bless different program bytes.
Once bound, same-generation registration cannot change or drop the binding;
that requires an adopted successor. An unbound legacy contract can opt in
without changing generations.

The program contains the outcome, success evidence, user constraints, working
assumptions and starting obligations. It is not a mutable status file. When
continuing existing research, identify which prior candidate or required
follow-up the frame advances, or record an explicit reason to defer it.

## Report the program delta in the diagnosis

For a run issued under a bound program, add this block to the existing diagnosis:

```json
{
  "program_progress": {
    "kind": "preparation",
    "criterion": "program.md / Success Evidence: deliver a usable candidate",
    "delta": "Input checks now pass; usable candidates remain at zero",
    "evidence_refs": ["ev-actual-run-seal-id"],
    "remaining": ["Retest the inherited candidate", "Establish the comparison baseline"],
    "next_action": "Run the inherited candidate through the existing checks"
  }
}
```

All six fields are required. `criterion`, `delta` and `next_action` are nonempty
text. `evidence_refs` must include this run's seal event id and may cite other
existing journal event ids. `remaining` is a list of unresolved obligations;
an empty list does not certify completion. Placeholders are refused.

| Kind | Author's claim |
| --- | --- |
| `outcome` | A result changed against the named program success criterion |
| `learning` | Evidence changed the hypothesis or next decision |
| `preparation` | Inputs, tools or execution readiness improved |
| `no_change` | No supported change to report |

The program binding follows issuance → run seal → diagnosis seal. A later
contract registration cannot relabel an earlier run's program. The progress
block is copied into the hash-chained diagnosis event so status does not depend
on a mutable hand-written status document or a later edit to the diagnosis file.

## Read progress without inventing success

`os/steer.py status` and `frame-health` expose `program_progress`: program
integrity, reported and unreported runs, declared kinds, the latest declaration,
and runs since the last **declared** outcome for that exact program binding.
Reports persist across generations that keep the binding. A different program
binding starts a separate projection; old evidence stays in the journal.

Frame-health also asks about alignment with the program, preparation detours
and inherited work. These questions are advisory. Notes still carry no execution
authority, and `aim` never consumes their prose or changes a target from them.

Validation checks shape, file identity and reference existence. It cannot prove
that a cited artifact establishes a criterion, that an assumption is necessary,
or that an `outcome` declaration is honest. Missing reports are unknown, not
`no_change`. `completion` is always `NOT_EVALUATED`; only the application's full
completion evidence and its designated owner can establish the external goal.
No automatic stop, approval, budget refund or new scoring metric is added.

## Existing projects

Contracts without `[program]` and their journals keep working. Their progress
is reported as `UNBOUND`, and old `SUPPORTED` diagnoses are not converted into
program outcomes. Finish already issued work first. Bind the program in a later
reviewed contract using the existing registration/adoption rules. Runs issued
before that binding, including migrated runs, keep the old diagnosis schema;
no historical judgment needs to be rewritten.
