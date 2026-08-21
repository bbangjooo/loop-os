#!/bin/sh
# Loop OS installer.
#
#   curl -fsSL https://raw.githubusercontent.com/bbangjooo/loop-os/main/install.sh | sh
#
# What it does:
#   1. Clones (or updates) the repo into $LOOP_OS_HOME (default: ~/loop-os).
#   2. Installs Python dependencies with uv.
#   3. Installs the agent skill into every harness it can find:
#        Claude Code -> ~/.claude/skills/loop-os/SKILL.md
#        Codex       -> ~/.agents/skills/loop-os/SKILL.md
#
# It never touches your projects, shell profile, or PATH. There is no CLI
# product and no daemon — the instruments in os/ are plain scripts run by path.

set -eu

REPO_URL="https://github.com/bbangjooo/loop-os.git"
LOOP_OS_HOME="${LOOP_OS_HOME:-$HOME/loop-os}"

info()  { printf '\033[1;34m==>\033[0m %s\n' "$1"; }
fail()  { printf '\033[1;31merror:\033[0m %s\n' "$1" >&2; exit 1; }

command -v git >/dev/null 2>&1 || fail "git is required. Install git and re-run."
command -v uv  >/dev/null 2>&1 || fail "uv is required. Install it first: curl -LsSf https://astral.sh/uv/install.sh | sh"

if [ -d "$LOOP_OS_HOME/.git" ]; then
    info "Updating existing checkout at $LOOP_OS_HOME"
    git -C "$LOOP_OS_HOME" pull --ff-only
else
    info "Cloning $REPO_URL into $LOOP_OS_HOME"
    git clone "$REPO_URL" "$LOOP_OS_HOME"
fi

info "Installing Python dependencies (uv sync)"
(cd "$LOOP_OS_HOME" && uv sync)

installed_skill=""
install_skill() {
    harness_name="$1"; skill_dir="$2"
    mkdir -p "$skill_dir"
    cp "$LOOP_OS_HOME/SKILL.md" "$skill_dir/SKILL.md"
    info "Installed skill for $harness_name -> $skill_dir/SKILL.md"
    installed_skill="yes"
}

# Claude Code
if [ -d "$HOME/.claude" ]; then
    install_skill "Claude Code" "$HOME/.claude/skills/loop-os"
fi

# Codex (skills live under ~/.agents/skills; ~/.codex marks an install)
if [ -d "$HOME/.codex" ] || [ -d "$HOME/.agents" ]; then
    install_skill "Codex" "$HOME/.agents/skills/loop-os"
fi

if [ -z "$installed_skill" ]; then
    info "No agent harness found (~/.claude or ~/.codex). Skill not installed."
    info "After installing a harness, copy it yourself:"
    info "  cp $LOOP_OS_HOME/SKILL.md ~/.claude/skills/loop-os/SKILL.md"
fi

info "Verifying (OS + kernel + benchmark gate)"
(cd "$LOOP_OS_HOME" && uv run python -m pytest tests/ kernel/tests/ bench/ -q) \
    || fail "Test suite failed — the checkout is not healthy."

info "Done. Loop OS is at $LOOP_OS_HOME"
