from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE / "app"))
from cafe import InvalidPlan, MENU, orders, score, validate
from policy import schedule

spec = importlib.util.spec_from_file_location("cafe_example_runner", HERE / "run.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def two_coffees():
    return [{"id": i, "arrival": 0, "drink": "espresso", **MENU["espresso"]} for i in range(2)]


def test_parallel_preparation_and_batching_have_real_benefit():
    jobs = two_coffees()
    assert validate(jobs, schedule(jobs)) == [6, 12]
    plan = [
        {"kind": "prep", "orders": [0], "start": 0},
        {"kind": "prep", "orders": [1], "start": 1},
        {"kind": "brew", "orders": [0, 1], "start": 2},
        {"kind": "serve", "orders": [0], "start": 6},
        {"kind": "serve", "orders": [1], "start": 7},
    ]
    assert validate(jobs, plan) == [7, 8]


@pytest.mark.parametrize("mutation", ["missing", "overlap", "arrival", "freshness", "duplicate", "nan"])
def test_invalid_shortcuts_are_rejected(mutation):
    jobs = two_coffees()
    plan = schedule(jobs)
    if mutation == "missing":
        plan.pop()
    elif mutation == "overlap":
        plan[3]["start"] = 0
    elif mutation == "arrival":
        jobs[0]["arrival"] = 1
    elif mutation == "freshness":
        plan[5]["start"] += 13
    elif mutation == "duplicate":
        plan[3]["orders"] = [0]
    else:
        plan[0]["start"] = float("nan")
    with pytest.raises(InvalidPlan):
        validate(jobs, plan)


def test_policy_cannot_rewrite_the_validation_input(tmp_path):
    policy = tmp_path / "cheat.py"
    policy.write_text("def schedule(orders):\n    orders.clear()\n    return []\n")
    with pytest.raises(InvalidPlan, match="missing"):
        score(policy, [0])


@pytest.mark.parametrize("body", [
    "import cafe\ncafe.validate=lambda jobs, plan: [0.0]*len(jobs)\ndef schedule(orders): return []\n",
    "print('{\"valid\": true, \"mean_wait\": 0}')\ndef schedule(orders): return []\n",
    "from time import perf_counter\nstamp = perf_counter()\n" + (HERE / "app/policy.py").read_text(),
    "clock = __import__('time')\n" + (HERE / "app/policy.py").read_text(),
])
def test_policy_cannot_replace_validator_or_inject_a_score(tmp_path, body):
    policy = tmp_path / "cheat.py"
    policy.write_text(body)
    with pytest.raises(InvalidPlan):
        score(policy, [0])
    assert not runner.grade_frozen(policy, [100])["valid"]


def test_paired_inputs_budget_and_frozen_comparison(tmp_path):
    pair = tmp_path / "pair"
    manifest = runner.prepare(pair, seed=3, budget=3)
    for name in ("orders.json", "objective.py", "policy.py", "config.json"):
        assert (pair / "control" / name).read_bytes() == (pair / "exploration" / name).read_bytes()
    assert not (pair / "control/cafe.py").exists()
    config = json.loads((pair / "control/config.json").read_text())
    assert "train_seeds" not in config and "holdout_seeds" not in config
    assert not set(manifest["train_seeds"]) & set(manifest["holdout_seeds"])
    assert orders(3000) == orders(3000) and orders(3000) != orders(3001)
    app = pair / "control"
    command = [sys.executable, "objective.py"]
    assert subprocess.run(command, cwd=app, capture_output=True).returncode == 0
    (app / "policy.py").write_text("def schedule(orders): return []\n")
    assert subprocess.run(command, cwd=app, capture_output=True).returncode == 5
    assert subprocess.run(command, cwd=app, capture_output=True).returncode == 4
    assert len((pair / "evaluations/control/trials.jsonl").read_text().splitlines()) == 3
    report = runner.compare(pair)
    assert not report["automatic_checks_passed"]  # invalid control and absent model metadata
    assert report["arms"]["control"]["holdout"]["valid"]  # invalid last edit cannot replace the incumbent
    assert report["arms"]["control"]["selected_trial"] == 1
    assert report["arms"]["exploration"]["holdout"]["valid"]
    with pytest.raises(ValueError, match="already frozen"):
        runner.compare(pair)


@pytest.mark.parametrize("tamper", [False, True])
def test_same_model_required_and_tampered_scorer_disqualifies(tmp_path, tamper):
    pair = tmp_path / "pair"
    manifest = runner.prepare(pair, seed=0, budget=2)
    manifest["session_limits"] = {"usd_per_arm": 2, "timeout_seconds": 60}
    runner.write_json(pair / "manifest.json", manifest)
    for arm, model in (("control", "model-a"), ("exploration", "model-b")):
        runner.write_json(pair / f"{arm}-session.json", {
            "is_error": False, "modelUsage": {model: {}}, "total_cost_usd": 0.2, "wall_seconds": 10, "study_tools_verified": True,
        })
    if tamper:
        (pair / "exploration/objective.py").write_text("print(0)\n")
    report = runner.compare(pair)
    assert not report["automatic_checks_passed"]
    assert report["arms"]["exploration"]["integrity_changes"] == (["objective.py"] if tamper else [])
    if not tamper:
        assert all(row["eligible"] for row in report["arms"].values())
    assert report["arms"]["exploration"]["holdout"]["valid"]  # clean coordinator scorer


@pytest.mark.parametrize("cost,seconds", [(None, 10), (float("nan"), 10), (100.0, 10), (0.2, None), (0.2, 100)])
def test_missing_invalid_or_excess_resource_usage_disqualifies(tmp_path, cost, seconds):
    pair = tmp_path / "pair"
    manifest = runner.prepare(pair, seed=0, budget=2)
    manifest["session_limits"] = {"usd_per_arm": 2, "timeout_seconds": 60}
    runner.write_json(pair / "manifest.json", manifest)
    for arm, amount in (("control", 0.2), ("exploration", cost)):
        runner.write_json(pair / f"{arm}-session.json", {
            "is_error": False, "modelUsage": {"same-model": {}}, "study_tools_verified": True,
            "total_cost_usd": amount, "wall_seconds": 10 if arm == "control" else seconds,
        })
    report = runner.compare(pair)
    assert report["arms"]["control"]["eligible"]
    assert not report["arms"]["exploration"]["session_within_limits"]
    assert not report["automatic_checks_passed"]


def test_valid_matched_pair_reports_a_comparable_tie(tmp_path):
    pair = tmp_path / "pair"
    manifest = runner.prepare(pair, seed=0, budget=2)
    manifest["session_limits"] = {"usd_per_arm": 2, "timeout_seconds": 60}
    runner.write_json(pair / "manifest.json", manifest)
    for arm in ("control", "exploration"):
        runner.write_json(pair / f"{arm}-session.json", {
            "is_error": False, "modelUsage": {"same-model": {}}, "study_tools_verified": True,
            "total_cost_usd": 0.2, "wall_seconds": 10,
        })
    report = runner.compare(pair)
    assert report["automatic_checks_passed"]
    assert report["protocol_review"] == "REQUIRED"
    assert report["provisional_holdout_delta_exploration_minus_control"] == 0


def test_stdio_tools_block_escape_and_protected_edits_without_spending_budget(tmp_path):
    pair = tmp_path / "pair"
    runner.prepare(pair, seed=4, budget=2)
    calls = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "read_file", "arguments": {"path": "../manifest.json"}}},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "write_file", "arguments": {"path": "orders.json", "content": "[]"}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "syntax_check", "arguments": {}}},
        {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "evaluate", "arguments": {}}},
        {"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {"name": "evaluate", "arguments": {}}},
    ]
    result = subprocess.run([sys.executable, str(HERE / "tools.py"), "--workspace", str(pair / "control")],
                            input="\n".join(json.dumps(c) for c in calls) + "\n", text=True,
                            capture_output=True, check=True)
    messages = [json.loads(line)["result"] for line in result.stdout.splitlines()]
    assert messages[1]["isError"] and messages[2]["isError"]
    assert json.loads(messages[3]["content"][0]["text"])["executed"] is False
    assert json.loads(messages[4]["content"][0]["text"])["exit_code"] == 0
    assert json.loads(messages[5]["content"][0]["text"])["exit_code"] == 4
    assert len((pair / "evaluations/control/trials.jsonl").read_text().splitlines()) == 2
