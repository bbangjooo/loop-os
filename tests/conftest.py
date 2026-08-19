from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from ros import journal
from ros.seal import seal_contract

CONTRACT_TEMPLATE = """\
schema = "ros2-contract-v1"

[project]
id = "toy"

[frame]
generation = 1
class = "toy_descent"
mechanism = "value.txt holds a number; smaller is strictly better and the agent can lower it."

[budget]
iterations_total = {total}

[agent]
command = ["python3", "{agent}"]
timeout_seconds = 60

[[stages]]
id = "main"
prompt = "Lower the number in value.txt by exactly 1."
iterations = {per_run}

[stages.objective]
command = ["python3", "{objective}"]
direction = "minimize"
margin = 1
target = 0
timeout_seconds = 30
proxy_license = "toy contract clause 1: the number itself is the goal, not a proxy."

[[stages.guards]]
id = "app-intact"
command = ["python3", "-c", "import pathlib,sys; sys.exit(0 if pathlib.Path('app.py').exists() else 1)"]
kind = "exit_zero"
timeout_seconds = 30
"""


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A git-backed toy application: objective = the number in value.txt."""
    root = tmp_path / "proj"
    root.mkdir()
    _git(root.parent, "init", "-q", "-b", "work", str(root))
    _git(root, "config", "user.email", "ros2@example.invalid")
    _git(root, "config", "user.name", "ROS2 Test")
    (root / "value.txt").write_text("10\n", encoding="utf-8")
    (root / "app.py").write_text("VALUE = 10\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "seed")
    return root


@pytest.fixture
def objective(tmp_path: Path) -> Path:
    path = tmp_path / "objective.py"
    path.write_text(
        "from pathlib import Path\nprint(Path('value.txt').read_text().strip())\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def agent(tmp_path: Path) -> Path:
    path = tmp_path / "agent.py"
    path.write_text(
        "from pathlib import Path\n"
        "p = Path('value.txt')\n"
        "p.write_text(str(int(p.read_text().strip()) - 1) + '\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    return path


def write_contract(project: Path, objective: Path, agent: Path, total: int = 6, per_run: int = 3) -> Path:
    path = project / "contract.toml"
    path.write_text(
        CONTRACT_TEMPLATE.format(total=total, per_run=per_run, objective=objective, agent=agent),
        encoding="utf-8",
    )
    return path


@pytest.fixture
def registered_project(project: Path, objective: Path, agent: Path) -> Path:
    """Bootstrapped journal + registered contract, ready for ros.aim."""
    write_contract(project, objective, agent)
    journal.append_event(project, "bootstrap.v1", {"project_id": "toy", "lineage": []})
    journal.ensure_gitignored(project)
    seal_contract(project)
    _git(project, "add", "-A")
    _git(project, "commit", "-q", "-m", "contract")
    return project
