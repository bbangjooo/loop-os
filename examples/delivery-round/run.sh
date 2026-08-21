#!/bin/sh
# The bundled Loop OS example: the same kernel run twice on the same problem —
# once bare ("loop only"), once governed by the OS.
#
#   sh examples/delivery-round/run.sh [target-dir]
#
# Every step below is a call to kernel/loop.py or an os/ instrument — nothing
# else. The application is app/ (evaluator, guard, agents, one data file); the
# judgment files a real agent would author live pre-written in judgments/, with
# the numbers the deterministic runs actually produce.

set -eu

LOOP_OS_HOME="$(CDPATH='' cd -- "$(dirname -- "$0")/../.." && pwd)"
EX="$LOOP_OS_HOME/examples/delivery-round"
BASE="${1:-${TMPDIR:-/tmp}/loop-os-example-$$}"
P1="$BASE/loop-only"
P2="$BASE/with-os"

step() { printf '\n\033[1;34m== %s\033[0m\n' "$1"; }
[ -e "$BASE" ] && { printf 'target %s already exists; pass a fresh path\n' "$BASE" >&2; exit 1; }

seed() { # seed <dir> <contract>
    mkdir -p "$1"
    cp "$EX"/app/* "$1/"
    cp "$EX/contracts/$2" "$1/contract.toml"
    git -C "$1" init -q -b work
    git -C "$1" config user.email "example@loop-os.invalid"
    git -C "$1" config user.name "Loop OS Example"
    git -C "$1" add -A && git -C "$1" commit -q -m "seed"
}

cd "$LOOP_OS_HOME"

aim_run() { # aim_run <dir> — aim, commit the spec, run the kernel
    uv run python os/aim.py --project "$1" --contract "$1/contract.toml"
    git -C "$1" add -A && git -C "$1" commit -q -m "spec"
    SPEC="$(cd "$1" && ls -d loop/runs/*/spec.yaml | tail -1)"
    uv run --directory "$1" --project "$LOOP_OS_HOME" \
      python "$LOOP_OS_HOME/kernel/loop.py" --repo "$1" run "$SPEC"
    SUMMARY="$1/$(dirname "$SPEC")/summary.json"
    LEDGER="$1/.git/experiment-loop/$(basename "$(dirname "$SPEC")" | sed 's/^[0-9-]*-//')/ledger.jsonl"
}

# ---------------------------------------------------------------- loop only --
step "LOOP ONLY: one frame, the whole budget, no governance"
seed "$P1" loop-only.toml
uv run python os/journal.py bootstrap --project "$P1" --project-id delivery-round-loop-only
uv run python os/seal.py contract --project "$P1"
aim_run "$P1"
SUMMARY1="$SUMMARY"
# ...and that is where "loop only" ends: nothing is sealed, nothing is judged,
# and no matter how long it keeps proposing, the frame never changes.

# ------------------------------------------------------------------ with OS --
step "WITH THE OS: generation 1 (adjacent swap), budget 30, three sealed runs"
seed "$P2" gen1.toml
uv run python os/journal.py bootstrap --project "$P2" --project-id delivery-round
uv run python os/seal.py contract --project "$P2"

OS_SUMMARIES=""
for n in 1 2 3; do
    step "with-os: generation 1, run $n"
    aim_run "$P2"
    uv run python os/seal.py run --project "$P2" --summary "$SUMMARY" --ledger "$LEDGER"
    uv run python os/seal.py diagnosis --project "$P2" --file "$EX/judgments/diagnosis-run$n.json"
    uv run python os/journal.py anchor --project "$P2"
    git -C "$P2" add -A && git -C "$P2" commit -q -m "anchor"
    OS_SUMMARIES="$OS_SUMMARIES $SUMMARY"
done

step "with-os: aim again — the budget refuses (this refusal IS the workflow)"
uv run python os/aim.py --project "$P2" --contract "$P2/contract.toml" || true

step "with-os: residual, rival note, dossier — the jump path"
uv run python os/steer.py residual --project "$P2"
NOTE_ID=$(uv run python os/note.py --project "$P2" --kind rival_draft --body "$EX/judgments/rival.json" \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['note_id'])")
uv run python os/steer.py dossier --project "$P2" --rival "$NOTE_ID" > "$P2/dossier.json"

step "with-os: jump — adopt the successor frame"
# review.json and approval.json are pre-written so the example runs unattended;
# in a real project they come from an independent session and from you.
cp "$EX/contracts/gen2.toml" "$P2/contract.toml"
uv run python os/jump.py adopt --project "$P2" \
  --dossier "$P2/dossier.json" --successor "$P2/contract.toml" \
  --review "$EX/judgments/review.json" --approval "$EX/judgments/approval.json"
git -C "$P2" add -A && git -C "$P2" commit -q -m "generation 2 contract"
uv run python os/seal.py contract --project "$P2"

step "with-os: generation 2 (2-opt), one run"
aim_run "$P2"
uv run python os/seal.py run --project "$P2" --summary "$SUMMARY" --ledger "$LEDGER"
uv run python os/seal.py diagnosis --project "$P2" --file "$EX/judgments/diagnosis-gen2.json"
uv run python os/journal.py anchor --project "$P2"
git -C "$P2" add -A && git -C "$P2" commit -q -m "anchor"
OS_SUMMARIES="$OS_SUMMARIES $SUMMARY"

step "status — where the governed project now stands"
uv run python os/journal.py status --project "$P2"

step "render the comparison chart (skipped if matplotlib is missing)"
python3 "$EX/plot.py" --loop-only "$SUMMARY1" --with-os $OS_SUMMARIES \
  --jump-at 30 --out "$BASE/loop-vs-os.png" || true

printf '\nexample projects left at %s\n' "$BASE"
