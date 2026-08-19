from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))  # make harness/problems importable

from harness import (  # noqa: F401  (re-exported for the test modules)
    _git,
    drive,
    issue_and_commit,
    make_project,
    read_ledger,
    read_trials,
    run_kernel,
)


@pytest.fixture
def scripts(tmp_path: Path) -> Path:
    """Directory OUTSIDE the worktree for agent scripts, so the kernel's
    `git clean -fd` cannot touch them (same rule real projects follow)."""
    path = tmp_path / "scripts"
    path.mkdir()
    return path
