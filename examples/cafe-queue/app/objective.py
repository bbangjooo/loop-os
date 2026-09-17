"""One charged training evaluation. The coordinator grades frozen policies separately."""
import hashlib
import json
import sys
from pathlib import Path

from cafe import score


def main():
    config = json.loads(Path("config.json").read_text())
    cache = Path(".evaluations")
    cache.mkdir(exist_ok=True)
    log = cache / "trials.jsonl"
    used = len(log.read_text().splitlines()) if log.exists() else 0
    if used >= config["eval_budget"]:
        print("EVAL_BUDGET_EXHAUSTED", file=sys.stderr)
        return 4
    policy = Path("policy.py")
    trial = {"trial": used + 1, "policy_sha256": hashlib.sha256(policy.read_bytes()).hexdigest()}
    # Charge invalid and interrupted attempts too; append before executing policy.
    with log.open("a") as handle:
        handle.write(json.dumps(trial) + "\n")
    try:
        result = score(policy, config["train_seeds"])
    except Exception as error:
        print(f"INVALID_POLICY: {type(error).__name__}: {error}", file=sys.stderr)
        return 5
    result_path = cache / f"result-{used + 1:03d}.json"
    result_path.write_text(json.dumps({**trial, **result}, indent=2) + "\n")
    print(json.dumps(result))
    print(f"{result['mean_wait']:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
