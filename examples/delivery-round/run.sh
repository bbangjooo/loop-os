#!/bin/sh
# One full Loop OS cycle on a throwaway example project.
#
#   sh examples/delivery-round/run.sh [target-dir]
#
# Default target: a fresh directory under $TMPDIR. Nothing outside it is touched.
# Every step below runs the real instruments — no mocks, no shortcuts.

set -eu

LOOP_OS_HOME="$(CDPATH='' cd -- "$(dirname -- "$0")/../.." && pwd)"
SEED="$LOOP_OS_HOME/examples/delivery-round/seed"
P="${1:-${TMPDIR:-/tmp}/loop-os-example-$$}"

step() { printf '\n\033[1;34m== %s\033[0m\n' "$1"; }

[ -e "$P" ] && { printf 'target %s already exists; pass a fresh path\n' "$P" >&2; exit 1; }

step "seed the project at $P"
mkdir -p "$P"
cp "$SEED/cities.json" "$SEED/tour.json" "$SEED/objective.py" "$SEED/guard_tour_valid.py" \
   "$SEED/agent.py" "$SEED/contract.toml" "$P/"
git -C "$P" init -q -b work
git -C "$P" config user.email "example@loop-os.invalid"
git -C "$P" config user.name "Loop OS Example"
git -C "$P" add -A
git -C "$P" commit -q -m "seed: the delivery round as the driver currently runs it"

cd "$LOOP_OS_HOME"

step "bootstrap the journal"
uv run python os/journal.py bootstrap --project "$P" --project-id delivery-round

step "seal the contract"
uv run python os/seal.py contract --project "$P" --contract "$P/contract.toml"

step "aim — compile the contract into a kernel spec"
uv run python os/aim.py --project "$P" --contract "$P/contract.toml"

step "commit the spec (the kernel refuses untracked specs)"
git -C "$P" add -A
git -C "$P" commit -q -m "spec"

SPEC="$(cd "$P" && ls -d loop/runs/*/spec.yaml | tail -1)"
LOOP_ID="$(basename "$(dirname "$SPEC")" | sed 's/^[0-9-]*-//')"

step "run the kernel — the only step that executes anything"
# The spec path is resolved against the working directory, so the kernel runs
# from inside the project even though the code lives here.
uv run --directory "$P" --project "$LOOP_OS_HOME" \
  python "$LOOP_OS_HOME/kernel/loop.py" --repo "$P" run "$SPEC"

step "seal the run"
uv run python os/seal.py run --project "$P" \
  --summary "$P/$(dirname "$SPEC")/summary.json" \
  --ledger "$P/.git/experiment-loop/$LOOP_ID/ledger.jsonl"

step "seal the diagnosis (in real use, the agent authors this)"
cat > "$P/diagnosis.json" <<'JSON'
{
  "verdict": "SUPPORTED",
  "what_moved": "tour length fell from 2015.947 to 1525.805 — 24% — over 8 iterations, of which 4 were accepted and 4 reverted; denominator 8",
  "mechanism_interpretation": "The contract's mechanism holds so far: reversing a segment removed crossings the seed tour had, and every accepted move kept the tour valid. Two of the rejections changed the length by nothing at all, which is the margin doing its job rather than the mechanism failing.",
  "counterfactual": "Without the agent the length would have stayed at 2015.947; objective.py only reads tour.json, and the guard confirms no city was dropped, so the fall cannot be an evaluator artifact.",
  "next_question": "Half the proposals were wasted. Does a blind 2-opt keep paying at this rate as the tour approaches the 621.0 target, or does the accept rate collapse once the easy crossings are gone?"
}
JSON
uv run python os/seal.py diagnosis --project "$P" --file "$P/diagnosis.json"

step "anchor the journal head into git"
uv run python os/journal.py anchor --project "$P"
git -C "$P" add -A
git -C "$P" commit -q -m "anchor"

step "status — where the project now stands"
uv run python os/journal.py status --project "$P"

step "render the result chart"
python3 "$LOOP_OS_HOME/examples/delivery-round/plot.py" \
  --cities "$P/cities.json" --before "$SEED/tour.json" --after "$P/tour.json" \
  --summary "$P/$(dirname "$SPEC")/summary.json" --out "$P/result.svg"

printf '\nexample project left at %s\n' "$P"
