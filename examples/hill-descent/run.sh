#!/bin/sh
# One full Loop OS cycle on a throwaway example project.
#
#   sh examples/hill-descent/run.sh [target-dir]
#
# Default target: a fresh directory under $TMPDIR. Nothing outside it is touched.
# Every step below runs the real instruments — no mocks, no shortcuts.

set -eu

LOOP_OS_HOME="$(CDPATH='' cd -- "$(dirname -- "$0")/../.." && pwd)"
SEED="$LOOP_OS_HOME/examples/hill-descent/seed"
P="${1:-${TMPDIR:-/tmp}/loop-os-example-$$}"

step() { printf '\n\033[1;34m== %s\033[0m\n' "$1"; }

[ -e "$P" ] && { printf 'target %s already exists; pass a fresh path\n' "$P" >&2; exit 1; }

step "seed the project at $P"
mkdir -p "$P"
cp "$SEED/value.txt" "$SEED/app.py" "$SEED/objective.py" "$SEED/agent.py" "$SEED/contract.toml" "$P/"
git -C "$P" init -q -b work
git -C "$P" config user.email "example@loop-os.invalid"
git -C "$P" config user.name "Loop OS Example"
git -C "$P" add -A
git -C "$P" commit -q -m "seed: value.txt = 10"

cd "$LOOP_OS_HOME"

step "bootstrap the journal"
uv run python os/journal.py bootstrap --project "$P" --project-id hill-descent

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
  "what_moved": "objective fell from 10 to 7 over 3 accepted iterations; denominator 3",
  "mechanism_interpretation": "The contract's mechanism holds: each iteration lowered value.txt by one and the guard kept passing, so the fall is the mechanism working rather than the evaluator breaking.",
  "counterfactual": "With no agent mutation the objective would have stayed at 10, since objective.py only reads value.txt and nothing else writes it.",
  "next_question": "The descent is linear and bounded by budget, not by difficulty — does the objective stay honest as it approaches the target of 0?"
}
JSON
uv run python os/seal.py diagnosis --project "$P" --file "$P/diagnosis.json"

step "anchor the journal head into git"
uv run python os/journal.py anchor --project "$P"
git -C "$P" add -A
git -C "$P" commit -q -m "anchor"

step "status — where the project now stands"
uv run python os/journal.py status --project "$P"

printf '\nexample project left at %s\n' "$P"
