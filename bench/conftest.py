from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make harness / problems / run importable for the bench test modules.
_BENCH_DIR = str(Path(__file__).parent)
if _BENCH_DIR not in sys.path:
    sys.path.append(_BENCH_DIR)


@pytest.fixture
def scripts(tmp_path: Path) -> Path:
    """Directory OUTSIDE the worktree for agent scripts, so the kernel's
    `git clean -fd` cannot touch them (same rule real projects follow)."""
    path = tmp_path / "scripts"
    path.mkdir()
    return path
