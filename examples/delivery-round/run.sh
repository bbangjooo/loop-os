#!/bin/sh
# The bundled Loop OS example: the same kernel run twice on the same problem —
# once bare ("loop only"), once governed by the OS. Fixed objective, fixed
# proposal seeds; the only difference is the OS around the loop.
#
#   sh examples/delivery-round/run.sh [target-dir]
#
# Everything happens in throwaway directories (default: under $TMPDIR).
# Every step calls the real instruments; the only thing faked is the agent.

set -eu

LOOP_OS_HOME="$(CDPATH='' cd -- "$(dirname -- "$0")/../.." && pwd)"
EX="$LOOP_OS_HOME/examples/delivery-round"
SEED="$EX/seed"
BASE="${1:-${TMPDIR:-/tmp}/loop-os-example-$$}"
P1="$BASE/loop-only"
P2="$BASE/with-os"

step() { printf '\n\033[1;34m== %s\033[0m\n' "$1"; }

[ -e "$BASE" ] && { printf 'target %s already exists; pass a fresh path\n' "$BASE" >&2; exit 1; }

seed_project() {
    dir="$1"; contract="$2"
    mkdir -p "$dir"
    cp "$SEED/cities.json" "$SEED/tour.json" "$SEED/objective.py" \
       "$SEED/guard_tour_valid.py" "$SEED/agent.py" "$SEED/agent2.py" "$dir/"
    cp "$SEED/$contract" "$dir/contract.toml"
    git -C "$dir" init -q -b work
    git -C "$dir" config user.email "example@loop-os.invalid"
    git -C "$dir" config user.name "Loop OS Example"
    git -C "$dir" add -A
    git -C "$dir" commit -q -m "seed"
}

cd "$LOOP_OS_HOME"

aim_commit_run() {
    proj="$1"
    uv run python os/aim.py --project "$proj" --contract "$proj/contract.toml"
    git -C "$proj" add -A && git -C "$proj" commit -q -m "spec"
    SPEC="$(cd "$proj" && ls -d loop/runs/*/spec.yaml | tail -1)"
    LOOP_ID="$(basename "$(dirname "$SPEC")" | sed 's/^[0-9-]*-//')"
    uv run --directory "$proj" --project "$LOOP_OS_HOME" \
      python "$LOOP_OS_HOME/kernel/loop.py" --repo "$proj" run "$SPEC"
    SUMMARY="$proj/$(dirname "$SPEC")/summary.json"
    LEDGER="$proj/.git/experiment-loop/$LOOP_ID/ledger.jsonl"
}

seal_cycle() {
    proj="$1"; mechanism="$2"
    uv run python os/seal.py run --project "$proj" --summary "$SUMMARY" --ledger "$LEDGER"
    python3 "$EX/make_diagnosis.py" "$SUMMARY" "$proj/diagnosis.json" "$mechanism"
    uv run python os/seal.py diagnosis --project "$proj" --file "$proj/diagnosis.json"
    uv run python os/journal.py anchor --project "$proj"
    git -C "$proj" add -A && git -C "$proj" commit -q -m "anchor"
}

# ---------------------------------------------------------------- loop only --
step "LOOP ONLY: one frame, the whole budget, no governance"
seed_project "$P1" contract-loop-only.toml
uv run python os/journal.py bootstrap --project "$P1" --project-id delivery-round-loop-only
uv run python os/seal.py contract --project "$P1" --contract "$P1/contract.toml"
aim_commit_run "$P1"
SUMMARY1="$SUMMARY"
# ...and that is where "loop only" ends: nothing is sealed, nothing is judged,
# and no matter how long it keeps proposing, the frame never changes.

# ------------------------------------------------------------------ with OS --
step "WITH THE OS: generation 1 (adjacent swap), budget 30, 3 runs"
seed_project "$P2" contract.toml
uv run python os/journal.py bootstrap --project "$P2" --project-id delivery-round
uv run python os/seal.py contract --project "$P2" --contract "$P2/contract.toml"

OS_SUMMARIES=""
for run_n in 1 2 3; do
    step "with-os: generation 1, run $run_n"
    aim_commit_run "$P2"
    seal_cycle "$P2" "adjacent swaps fix neighboring inversions"
    OS_SUMMARIES="$OS_SUMMARIES $SUMMARY"
done

step "with-os: aim again — the budget refuses (this refusal IS the workflow)"
uv run python os/aim.py --project "$P2" --contract "$P2/contract.toml" || true

step "with-os: residual — what the stall looks like as evidence"
uv run python os/steer.py residual --project "$P2"

step "with-os: author the rival frame and its dossier"
cat > "$P2/rival.json" <<'JSON'
{
  "commitment_rejected": "adjacent_swap: the class stopped producing accepted moves while the round still crosses itself",
  "proposed_frame": "two_opt: reverse one whole segment per iteration",
  "mechanism": "A crossing is removed by reversing the segment between the two crossing edges — a move no sequence of single adjacent swaps can make without passing through longer tours first.",
  "falsifier": "If accepted reversals also dry up while crossings remain, the successor class is wrong too."
}
JSON
NOTE_ID=$(uv run python os/note.py --project "$P2" --kind rival_draft --body "$P2/rival.json" \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['note_id'])")
uv run python os/steer.py dossier --project "$P2" --rival "$NOTE_ID" > "$P2/dossier.json"

# In real use these two files are written by an independent reviewer and by you.
# The example scripts them so it can run unattended — which is exactly why a real
# project must not.
cat > "$P2/review.json" <<'JSON'
{
  "reviewer": "scripted-for-the-example (a real project uses a separate session or model)",
  "independent": true,
  "verdict": "PASS",
  "notes": "Successor mechanism names a move the rejected class cannot make, and carries its own falsifier."
}
JSON
cat > "$P2/approval.json" <<'JSON'
{
  "approved_by": "the human running this example",
  "statement": "Adopt two_opt as generation 2; the adjacent_swap budget is spent and its falsifier fired."
}
JSON

step "with-os: jump — adopt the successor frame"
cp "$SEED/contract-gen2.toml" "$P2/contract-gen2.toml"
uv run python os/jump.py adopt --project "$P2" \
  --dossier "$P2/dossier.json" --successor "$P2/contract-gen2.toml" \
  --review "$P2/review.json" --approval "$P2/approval.json"
cp "$P2/contract-gen2.toml" "$P2/contract.toml"
git -C "$P2" add -A && git -C "$P2" commit -q -m "generation 2 contract"
uv run python os/seal.py contract --project "$P2" --contract "$P2/contract.toml"

step "with-os: generation 2 (2-opt), one run"
aim_commit_run "$P2"
seal_cycle "$P2" "segment reversal removes crossings"
OS_SUMMARIES="$OS_SUMMARIES $SUMMARY"

step "status — where the governed project now stands"
uv run python os/journal.py status --project "$P2"

step "render the comparison chart"
python3 "$EX/plot.py" --loop-only "$SUMMARY1" --with-os $OS_SUMMARIES \
  --jump-at 30 --out "$BASE/loop-vs-os.png"

printf '\nexample projects left at %s\n' "$BASE"
