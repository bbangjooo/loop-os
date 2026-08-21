#!/bin/sh
# The bundled Loop OS example: the same kernel run twice on the same problem.
#
#   sh examples/delivery-round/run.sh [target-dir]
#
# Fairness: both paths use the same frame (class, mechanism, agent, objective,
# guard, margin — diff contracts/gen1.toml contracts/loop-only.toml) and the
# same total of 80 iterations. The only difference is how the 80 are governed:
# loop-only spends them in one undivided run; with-os spends 30 across three
# sealed runs, then 50 more in a successor frame licensed by a jump.
#
# Every command below is kernel/loop.py or an os/ instrument. The application
# lives in app/, the frames in contracts/, and the judgment files a real agent
# and human would author in judgments/.

set -eu

LOOP_OS_HOME="$(CDPATH='' cd -- "$(dirname -- "$0")/../.." && pwd)"
EX="$LOOP_OS_HOME/examples/delivery-round"
BASE="${1:-${TMPDIR:-/tmp}/loop-os-example-$$}"

step() { printf '\n\033[1;34m== %s\033[0m\n' "$1"; }
[ -e "$BASE" ] && { printf 'target %s already exists; pass a fresh path\n' "$BASE" >&2; exit 1; }
cd "$LOOP_OS_HOME"

seed() { # seed <dir> <contract>
    mkdir -p "$1"
    cp "$EX"/app/* "$1/"
    cp "$EX/contracts/$2" "$1/contract.toml"
    git -C "$1" init -q -b work
    git -C "$1" config user.email "example@loop-os.invalid"
    git -C "$1" config user.name "Loop OS Example"
    git -C "$1" add -A && git -C "$1" commit -q -m "seed"
}

aim_run() { # aim_run <dir> — aim, commit the spec, run the kernel
    uv run python os/aim.py --project "$1" --contract "$1/contract.toml"
    git -C "$1" add -A && git -C "$1" commit -q -m "spec"
    SPEC="$(cd "$1" && ls -d loop/runs/*/spec.yaml | tail -1)"
    uv run --directory "$1" --project "$LOOP_OS_HOME" \
      python "$LOOP_OS_HOME/kernel/loop.py" --repo "$1" run "$SPEC"
    SUMMARY="$1/$(dirname "$SPEC")/summary.json"
    LEDGER="$1/.git/experiment-loop/$(basename "$(dirname "$SPEC")" | sed 's/^[0-9-]*-//')/ledger.jsonl"
}

seal_cycle() { # seal_cycle <dir> <diagnosis-file> — seal the run, its diagnosis, and anchor
    uv run python os/seal.py run --project "$1" --summary "$SUMMARY" --ledger "$LEDGER"
    uv run python os/seal.py diagnosis --project "$1" --file "$EX/judgments/$2"
    uv run python os/journal.py anchor --project "$1"
    git -C "$1" add -A && git -C "$1" commit -q -m "anchor"
}

run_loop_only() {
    P="$BASE/loop-only"
    step "LOOP ONLY: one frame, all 80 iterations, no governance"
    seed "$P" loop-only.toml
    uv run python os/journal.py bootstrap --project "$P" --project-id delivery-round-loop-only
    uv run python os/seal.py contract --project "$P"
    aim_run "$P"
    SUMMARY_LOOP_ONLY="$SUMMARY"
    # ...and that is where "loop only" ends: nothing is sealed, nothing is
    # judged, and no matter how long it proposes, the frame never changes.
}

run_with_os() {
    P="$BASE/with-os"
    step "WITH THE OS: generation 1 (adjacent swap), budget 30, three sealed runs"
    seed "$P" gen1.toml
    uv run python os/journal.py bootstrap --project "$P" --project-id delivery-round
    uv run python os/seal.py contract --project "$P"

    OS_SUMMARIES=""
    for n in 1 2 3; do
        step "with-os: generation 1, run $n"
        aim_run "$P"
        seal_cycle "$P" "diagnosis-run$n.json"
        OS_SUMMARIES="$OS_SUMMARIES $SUMMARY"
    done

    step "with-os: aim again — the budget refuses (this refusal IS the workflow)"
    uv run python os/aim.py --project "$P" --contract "$P/contract.toml" || true

    step "with-os: residual, rival note, dossier — the jump path"
    uv run python os/steer.py residual --project "$P"
    NOTE_ID=$(uv run python os/note.py --project "$P" --kind rival_draft --body "$EX/judgments/rival.json" \
      | python3 -c "import json,sys; print(json.load(sys.stdin)['note_id'])")
    uv run python os/steer.py dossier --project "$P" --rival "$NOTE_ID" > "$P/dossier.json"

    step "with-os: jump — adopt the successor frame"
    # review.json and approval.json are pre-written so the example runs
    # unattended; in a real project they come from an independent session and you.
    cp "$EX/contracts/gen2.toml" "$P/contract.toml"
    uv run python os/jump.py adopt --project "$P" \
      --dossier "$P/dossier.json" --successor "$P/contract.toml" \
      --review "$EX/judgments/review.json" --approval "$EX/judgments/approval.json"
    git -C "$P" add -A && git -C "$P" commit -q -m "generation 2 contract"
    uv run python os/seal.py contract --project "$P"

    step "with-os: generation 2 (2-opt), one run"
    aim_run "$P"
    seal_cycle "$P" "diagnosis-gen2.json"
    OS_SUMMARIES="$OS_SUMMARIES $SUMMARY"
}

compare() {
    step "compare: where the governed project stands"
    uv run python os/journal.py status --project "$BASE/with-os"
    step "compare: chart (skipped if matplotlib is missing)"
    python3 "$EX/plot.py" --loop-only "$SUMMARY_LOOP_ONLY" --with-os $OS_SUMMARIES \
      --jump-at 30 --out "$BASE/loop-vs-os.png" || true
    printf '\nexample projects left at %s\n' "$BASE"
}

run_loop_only
run_with_os
compare
