"""Prepare a reproducible cafe search ablation, run two fresh sessions, grade frozen code."""
from __future__ import annotations

import argparse
import contextlib
import io
from contextlib import ExitStack
import hashlib
import json
import math
import os
import random
import signal
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / "app"))
from cafe import orders, score, screen_source

TASK = """Improve policy.py to reduce average time from each customer's arrival to service.
This is a deterministic toy cafe with one barista and one automatic machine.
Each of 12 orders needs prep -> brew -> serve. Prep and serve occupy the barista;
brew occupies only the machine. The machine can brew up to two orders together
if their family and brew duration match. Durations come from the order, never
from the proposed plan. Serving must start within 12 seconds after brewing.
Every order needs each operation exactly once; respect arrivals and resource
exclusivity. A plan is a list of {kind, orders: [integer ids], start: integer}.
schedule(orders) must be a general pure function using only the standard library;
it must not inspect files, seeds, process state, or evaluator internals at runtime.
Allowed policy imports: math, heapq, itertools, functools, collections, dataclasses,
typing, bisect, array, statistics, copy, __future__. No time/perf_counter, random, os, sys,
reflection or dynamic execution. Use fixed node/iteration limits for search,
not a clock deadline. Identical input must produce an identical plan.
The input includes the complete day's orders, so advance scheduling is allowed.
Keep the policy efficient: grading a batch of 64 days has a 15-second limit.

Only edit policy.py and research notes. orders.json contains the eight training
days with exact durations and arrivals. Use the cafe evaluate tool for ALL
candidate execution: quality, validity checks AND runtime profiling. Syntax-only
compilation is free. Do not generate extra days, import the private evaluator,
replicate it or test candidate schedules outside this command. Invalid attempts
also cost a call. Do not run concurrent evaluations or edit protected files/logs.
The evaluation tool executes the coordinator; that is not permission to read its code or
files outside this workspace. Final code will be frozen and graded
on additional days not supplied to you. Stay inside this workspace, use no web,
other sessions, installed skills, examples or outside solutions. Do not spawn
agents. There is no shell or arbitrary execution tool. The starting policy was
already evaluated and charged once; read baseline.json. The total evaluation
budget includes that baseline. The coordinator selects the lowest training score
among valid evaluated snapshots (earliest wins exact ties) for final grading.
An unevaluated last edit will not replace the measured incumbent.
Record your hypothesis, falsifier, trial interpretation and final rationale in
research.json. Final response: what changed, final measured score and uncertainty.
Keep all scratch files and backups inside this workspace under scratch/.
Do not use /tmp or any other outside path for candidate backups.

This is an isolated test of search instructions, not a full Loop OS cycle.
The evaluator and its budget are already provided. Do not bootstrap a journal,
create contracts, call the kernel, install dependencies, or change the task.
"""

CONTROL = """Use the original mechanism-first approach: inspect the starting solution,
form a falsifiable mechanism for improving it, implement and measure a candidate,
interpret the result, and use what you learned for the next candidate. Keep
failures visible and respect the fixed objective, validity constraints and budget.
"""


def write_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def bounded(command, *, cwd=None, timeout=15, stdout_path=None, env=None):
    """Stop the owned process group before freezing outputs after a timeout."""
    with ExitStack() as stack:
        output = stack.enter_context(stdout_path.open("w")) if stdout_path else subprocess.PIPE
        with subprocess.Popen(command, cwd=cwd, stdout=output, stderr=subprocess.PIPE,
                              text=True, start_new_session=True, env=env) as process:
            try:
                stdout, stderr = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                if os.name == "posix":
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
                process.communicate()
                raise
            if stdout_path:
                stdout = stdout_path.read_text()
            return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def prepare(out: Path, seed: int, budget: int) -> dict:
    if out.exists():
        raise ValueError("output already exists; use a fresh directory")
    if budget < 1 or seed < 0:
        raise ValueError("budget must be positive and seed nonnegative")
    out.mkdir(parents=True)
    reference = (ROOT / "references/frame-exploration.md").read_text()
    extra = reference.split("## Generate before comparing\n", 1)[1].split("## Record and hand off", 1)[0]
    scenario_seeds = random.Random(seed).sample(range(2**31), 72)
    train = scenario_seeds[:8]
    # Coordinator-side holdout is intentionally not copied into either workspace.
    holdout = scenario_seeds[8:]
    manifest = {"schema": "cafe-search-ablation-v3", "seed": seed,
                "eval_budget": budget, "train_seeds": train, "holdout_seeds": holdout,
                "reference_sha256": hashlib.sha256(reference.encode()).hexdigest(),
                "source_sha256": {name: hashlib.sha256((HERE / "app" / name).read_bytes()).hexdigest()
                                  for name in ("cafe.py", "objective.py", "policy.py")},
                "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "tools_sha256": hashlib.sha256((HERE / "tools.py").read_bytes()).hexdigest(),
                "protected_hashes": {},
                "study": "search-instruction ablation, not full outer-loop comparison"}
    for arm in ("control", "exploration"):
        app = out / arm
        app.mkdir()
        for name in ("objective.py", "policy.py"):
            shutil.copy2(HERE / "app" / name, app / name)
        write_json(app / "config.json", {"eval_budget": budget, "evaluator_command":
                   [sys.executable, str(Path(__file__).resolve()), "evaluate", "--workspace"]})
        write_json(app / "orders.json", [orders(s) for s in train])
        (app / ".gitignore").write_text("__pycache__/\n")
        guidance = CONTROL
        if arm == "exploration":
            guidance += ("\nApply this additional generation/comparison procedure. Before evaluating a "
                         "changed policy, record candidates, structural mappings, falsifiers and desk "
                         "comparison in exploration.json; use random_cue before selecting the first "
                         "candidate. Update the record as evidence arrives. References to contract/"
                         "evaluator workflow below mean the provided evaluate tool and fixed budget.\n\n") + extra
        (app / "TASK.md").write_text(TASK + "\n" + guidance)
        manifest["protected_hashes"][arm] = {
            name: hashlib.sha256((app / name).read_bytes()).hexdigest()
            for name in ("objective.py", "config.json", "orders.json", "TASK.md")
        }
        for args in (("init", "-q", "-b", "study"),
                     ("config", "user.email", "cafe@example.invalid"),
                     ("config", "user.name", "Cafe Example"),
                     ("add", "-A"), ("commit", "-q", "-m", "Initial cafe task")):
            subprocess.run(["git", *args], cwd=app, check=True, capture_output=True)
    write_json(out / "manifest.json", manifest)
    for arm in ("control", "exploration"):
        with contextlib.redirect_stdout(io.StringIO()):
            code = evaluate(out / arm)
        if code != 0:
            raise RuntimeError("the supplied baseline failed evaluation")
        result = json.loads((out / "evaluations" / arm / "result-001.json").read_text())
        baseline = {k: result[k] for k in ("mean_wait", "p95_wait", "max_wait", "evaluations_remaining")}
        write_json(out / arm / "baseline.json", baseline)
        manifest["protected_hashes"][arm]["baseline.json"] = hashlib.sha256((out / arm / "baseline.json").read_bytes()).hexdigest()
    write_json(out / "manifest.json", manifest)
    return manifest


def evaluate(workspace: Path) -> int:
    app = workspace.resolve()
    if app.name not in ("control", "exploration"):
        raise ValueError("not a prepared study workspace")
    manifest = json.loads((app.parent / "manifest.json").read_text())
    log_dir = app.parent / "evaluations" / app.name
    log_dir.mkdir(parents=True, exist_ok=True)
    log = log_dir / "trials.jsonl"
    used = len(log.read_text().splitlines()) if log.exists() else 0
    if used >= manifest["eval_budget"]:
        print("EVAL_BUDGET_EXHAUSTED", file=sys.stderr)
        return 4
    source = (app / "policy.py").read_bytes()
    trial = {"trial": used + 1, "policy_sha256": hashlib.sha256(source).hexdigest()}
    with log.open("a") as handle:
        handle.write(json.dumps(trial) + "\n")
    (log_dir / f"policy-{used + 1:03d}.py").write_bytes(source)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="cafe-evaluation-") as tmp:
        candidate = Path(tmp) / "policy.py"
        candidate.write_bytes(source)
        result = grade_frozen(candidate, manifest["train_seeds"])
    result.update(trial)
    result["evaluation_seconds"] = time.monotonic() - started
    result["evaluations_remaining"] = manifest["eval_budget"] - used - 1
    write_json(log_dir / f"result-{used + 1:03d}.json", result)
    if not result["valid"]:
        print("INVALID_POLICY: " + result["error"], file=sys.stderr)
        return 5
    print(json.dumps(result))
    print(f"{result['mean_wait']:.6f}")
    return 0


def grade_frozen(policy: Path, seeds: list[int]) -> dict:
    # A subprocess bounds pathological candidate execution. Only the frozen source
    # is loaded; final grading uses this checkout's scorer, never an edited copy.
    command = [sys.executable, str(Path(__file__).resolve()), "_grade",
               "--policy", str(policy), "--seeds", json.dumps(seeds)]
    try:
        result = bounded(command, timeout=15)
        if result.returncode:
            return {"valid": False, "error": result.stderr[-1000:]}
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        return {"valid": False, "error": "policy exceeded 15 seconds"}
    except json.JSONDecodeError:
        return {"valid": False, "error": "policy polluted the grading output"}


def compare(out: Path) -> dict:
    manifest = json.loads((out / "manifest.json").read_text())
    if manifest["schema"] != "cafe-search-ablation-v3":
        raise ValueError("use the matching runner for this historical study schema")
    for name, digest in manifest["source_sha256"].items():
        if hashlib.sha256((HERE / "app" / name).read_bytes()).hexdigest() != digest:
            raise ValueError("example sources changed since preparation; grade with the original checkout")
    frozen = out / "frozen"
    if frozen.exists():
        raise ValueError("comparison already frozen; use another pair for a new run")
    frozen.mkdir()
    # Freeze BOTH arms before revealing either holdout result.
    selections = {}
    for arm in ("control", "exploration"):
        log_dir = out / "evaluations" / arm
        valid = [json.loads(p.read_text()) for p in log_dir.glob("result-*.json")]
        valid = [r for r in valid if r["valid"]]
        selected = min(valid, key=lambda r: (r["mean_wait"], r["trial"]))
        source = log_dir / f"policy-{selected['trial']:03d}.py"
        if hashlib.sha256(source.read_bytes()).hexdigest() != selected["policy_sha256"]:
            raise ValueError("measured snapshot digest changed")
        shutil.copy2(source, frozen / f"{arm}.py")
        selections[arm] = selected
    baseline = grade_frozen(HERE / "app/policy.py", manifest["holdout_seeds"])
    rows = {}
    for arm in ("control", "exploration"):
        app = out / arm
        source = frozen / f"{arm}.py"
        row = {"policy_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
               "selected_trial": selections[arm]["trial"],
               "train": grade_frozen(source, manifest["train_seeds"]),
               "holdout": grade_frozen(source, manifest["holdout_seeds"])}
        changed = []
        for name, digest in manifest["protected_hashes"][arm].items():
            if not (app / name).exists() or hashlib.sha256((app / name).read_bytes()).hexdigest() != digest:
                changed.append(name)
        trials = out / "evaluations" / arm / "trials.jsonl"
        row["evaluations_logged"] = len(trials.read_text().splitlines()) if trials.exists() else 0
        row["integrity_changes"] = changed
        row["training_score_reproduced"] = row["train"]["valid"] and math.isclose(row["train"]["mean_wait"], selections[arm]["mean_wait"], abs_tol=1e-9)
        row["eligible"] = not changed and row["evaluations_logged"] <= manifest["eval_budget"] and row["training_score_reproduced"] and row["holdout"]["valid"]
        session = out / f"{arm}-session.json"
        if session.exists():
            data = json.loads(session.read_text())
            row["session"] = {k: data.get(k) for k in ("is_error", "subtype", "modelUsage", "usage", "total_cost_usd", "duration_ms", "wall_seconds", "study_tools_verified")}
            limits = manifest.get("session_limits", {})
            def within(value, ceiling):
                return type(value) in (float, int) and math.isfinite(value) and 0 <= value <= ceiling
            row["session_within_limits"] = (
                within(data.get("total_cost_usd"), limits.get("usd_per_arm", -1))
                and within(data.get("wall_seconds"), limits.get("timeout_seconds", -1))
            )
            row["eligible"] = row["eligible"] and not data.get("is_error", True) and row["session_within_limits"] and data.get("study_tools_verified") is True
        rows[arm] = row
    comparable = all(r["eligible"] for r in rows.values())
    models = [set(r.get("session", {}).get("modelUsage") or {}) for r in rows.values()]
    if not models[0] or models[0] != models[1]:
        comparable = False
    report = {"manifest": manifest, "fifo_holdout": baseline, "arms": rows,
              "automatic_checks_passed": comparable, "protocol_review": "REQUIRED",
              "provisional_holdout_delta_exploration_minus_control":
              rows["exploration"]["holdout"]["mean_wait"] - rows["control"]["holdout"]["mean_wait"] if comparable else None,
              "interpretation": "Automatic checks do not certify session compliance. Obtain an independent tool-trace/protocol review before interpreting the provisional delta. One pair is a pilot, not evidence of general creativity improvement. Negative delta favors exploration."}
    write_json(out / "comparison.json", report)
    return report


def pilot(out: Path, seed: int, budget: int, model: str | None, usd: float, timeout: int, effort: str):
    if not math.isfinite(usd) or usd <= 0 or timeout <= 0:
        raise ValueError("USD and time limits must be positive and finite")
    if shutil.which("claude") is None:
        raise ValueError("pilot requires a configured Claude Code CLI; demo needs no model")
    manifest = prepare(out, seed, budget)
    manifest["session_limits"] = {"requested_model": model, "usd_per_arm": usd,
                                  "timeout_seconds": timeout, "effort": effort}
    manifest["claude_version"] = subprocess.check_output(["claude", "--version"], text=True).strip()
    write_json(out / "manifest.json", manifest)
    order = ["control", "exploration"]
    random.Random(seed).shuffle(order)
    write_json(out / "execution-order.json", order)
    for arm in order:
        config = out / f"{arm}-mcp.json"
        write_json(config, {"mcpServers": {"cafe": {"command": sys.executable,
                   "args": [str(HERE / "tools.py"), "--workspace", str(out / arm)]}}})
        prompt = (f"Read TASK.md and complete the study task. This session has at most {timeout} seconds "
                  f"and ${usd} of reported API usage. Finish your best valid policy and notes before "
                  "the limits; you do not need to use every evaluation. Default to a simple working "
                  "improvement before expensive refinements.")
        command = ["claude", "-p", prompt, "--effort", effort,
                   "--setting-sources", "", "--settings", '{"disableAllHooks":true,"autoMemoryEnabled":false}',
                   "--disable-slash-commands", "--output-format", "stream-json", "--verbose",
                   "--tools", "", "--mcp-config", str(config), "--strict-mcp-config",
                   "--allowedTools", "mcp__cafe__*",
                   "--permission-mode", "dontAsk", "--no-session-persistence", "--max-budget-usd", str(usd)]
        if model:
            command += ["--model", model]
        child_env = dict(os.environ, CLAUDE_CODE_DISABLE_CLAUDE_MDS="1",
                         CLAUDE_CODE_DISABLE_AUTO_MEMORY="1",
                         CLAUDE_CODE_DISABLE_TERMINAL_TITLE="1", CLAUDE_CODE_EFFORT_LEVEL=effort)
        print(f"Starting {arm}", flush=True)
        started = time.monotonic()
        try:
            run = bounded(command, cwd=out / arm, timeout=timeout,
                          stdout_path=out / f"{arm}-session.jsonl", env=child_env)
            (out / f"{arm}-stderr.log").write_text(run.stderr)
            (out / f"{arm}-session.jsonl").write_text(run.stdout)
            try:
                events = [json.loads(line) for line in run.stdout.splitlines() if line.strip()]
                result = next(e for e in reversed(events) if e.get("type") == "result")
                init = next(e for e in events if e.get("subtype") == "init")
                available = init.get("tools", [])
                result["study_tools_verified"] = bool(available) and all(t.startswith("mcp__cafe__") or t == "ToolSearch" for t in available) and any(t.endswith("__evaluate") for t in available)
                if not result["study_tools_verified"]:
                    result.update(is_error=True, error="study-only MCP tools were not the active tool set")
            except (json.JSONDecodeError, StopIteration):
                result = {"is_error": True, "error": run.stdout[-2000:]}
            if run.returncode:
                result["is_error"] = True
        except subprocess.TimeoutExpired:
            result = {"is_error": True, "error": "session timeout"}
        result["wall_seconds"] = time.monotonic() - started
        write_json(out / f"{arm}-session.json", result)
        print(f"Finished {arm}; error={result.get('is_error')}", flush=True)
    print(json.dumps(compare(out), indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare", "pilot"):
        p = sub.add_parser(name)
        p.add_argument("--out", type=Path, required=True)
        p.add_argument("--seed", type=int, default=0)
        p.add_argument("--eval-budget", type=int, default=12)
        if name == "pilot":
            p.add_argument("--model", help="omit to use the isolated CLI default; pass a model to pin it")
            p.add_argument("--usd-per-arm", type=float, default=2.0)
            p.add_argument("--timeout", type=int, default=600)
            p.add_argument("--effort", choices=("low", "medium", "high", "xhigh", "max"), default="low")
    p = sub.add_parser("compare")
    p.add_argument("--out", type=Path, required=True)
    sub.add_parser("demo")
    p = sub.add_parser("evaluate")
    p.add_argument("--workspace", type=Path, required=True)
    p = sub.add_parser("_grade")
    p.add_argument("--policy", type=Path, required=True)
    p.add_argument("--seeds", required=True)
    args = parser.parse_args()
    if args.command == "_grade":
        print(json.dumps(score(args.policy, json.loads(args.seeds))))
    elif args.command == "evaluate":
        raise SystemExit(evaluate(args.workspace))
    elif args.command == "demo":
        print(json.dumps(score(HERE / "app/policy.py", list(range(8))), indent=2))
    elif args.command == "prepare":
        print(json.dumps(prepare(args.out.resolve(), args.seed, args.eval_budget), indent=2))
    elif args.command == "compare":
        print(json.dumps(compare(args.out.resolve()), indent=2))
    else:
        pilot(args.out.resolve(), args.seed, args.eval_budget, args.model, args.usd_per_arm, args.timeout, args.effort)


if __name__ == "__main__":
    main()
