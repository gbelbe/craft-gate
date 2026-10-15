#!/usr/bin/env bash
# Install or update craft-gate in a target repo.
#
# Usage:
#   bash bootstrap.sh [target-dir]      # default target: current directory
#
# Run this from inside a checkout of craft-gate itself (clone a tagged
# release rather than piping this over the network — see README.md):
#   git clone --branch vX.Y.Z --depth 1 https://github.com/gbelbe/craft-gate /tmp/craft-gate
#   bash /tmp/craft-gate/bootstrap.sh ~/code/my-project
#
# Only touches files this tool fully owns — the lists below, and
# .craft-gate-version (a plain-text marker of which release this checkout
# came from — see templates/update-check.yml, which reads it to detect
# drift). It never edits AGENTS.md, .pre-commit-config.yaml, or your CI
# workflow — those vary too much per project to auto-merge safely; INSTALL.md
# says what to add and where. Safe to re-run any time to pull an update.
set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${1:-.}"

# What this tool owns. Paths are the same in the source checkout and the target...
SHIPPED=(
  CRAFTSMANSHIP.md
  catalog.yaml
  scripts/check_tidy_ratchet.sh
  scripts/report_tidy_history.sh
  scripts/craftcov.py
  scripts/check_refactor_first.py
  scripts/check_complexity_ratchet.py
  scripts/craftcov_pr_comment.py
  scripts/check_mutation_ratchet.py
  scripts/mutation_plan.py
  scripts/gate_config.py
  scripts/design_review.py
  scripts/config_loosening.py
  # helpers the gate scripts import — they must travel with them
  scripts/gate-requirements.txt
  scripts/gitdiff.py
  scripts/astfuncs.py
  scripts/gate_timing.py
  scripts/ci_history.py
)
# ...except these, which live elsewhere in the source: "source:target".
RELOCATED=(
  skills/tidy-first/SKILL.md:.claude/skills/tidy-first/SKILL.md
  skills/craft-review/SKILL.md:.claude/skills/craft-review/SKILL.md
  agents/craft-reviewer.md:.claude/agents/craft-reviewer.md
  templates/local-craft-gate.sh:scripts/local-craft-gate.sh
)
# craftcov.py is a facade over this package; it ships as a unit.
PACKAGE=scripts/craftcov_core

if [[ ! -d "$TARGET/.git" ]]; then
  echo "✗ '$TARGET' doesn't look like a git repo root (no .git/ found)." >&2
  exit 1
fi

echo "Installing/updating craft-gate in $TARGET ..."

# Plain `cp` refuses when src and dst resolve to the literal same file — true
# whenever this runs against craft-gate's own checkout (self-application) and
# possible for any target already fully up to date. Compare content instead
# of paths: skip only when the bytes already match, so both cases work and a
# genuine update still copies.
copy_file() {
  local src="$1" dst="$2"
  mkdir -p "$(dirname "$dst")"
  if [[ -f "$dst" ]] && cmp -s "$src" "$dst"; then
    return 0
  fi
  cp "$src" "$dst"
}

# Scripts are run directly, so they keep the source's executable bit (and a
# library like gitdiff.py, which is only imported, stays non-executable).
install_file() {
  local src="$1" dst="$2"
  copy_file "$SRC_DIR/$src" "$TARGET/$dst"
  if [[ -x "$SRC_DIR/$src" ]]; then
    chmod +x "$TARGET/$dst"
  fi
}

for path in "${SHIPPED[@]}"; do
  install_file "$path" "$path"
done
for pair in "${RELOCATED[@]}"; do
  install_file "${pair%%:*}" "${pair#*:}"
done

# Ship the package, and drop modules an earlier release shipped that this one no longer has.
mkdir -p "$TARGET/$PACKAGE"
for src in "$SRC_DIR/$PACKAGE"/*.py; do
  copy_file "$src" "$TARGET/$PACKAGE/$(basename "$src")"
done
for dst in "$TARGET/$PACKAGE"/*.py; do
  [[ -f "$SRC_DIR/$PACKAGE/$(basename "$dst")" ]] || rm -f "$dst"
done

# Record which release this came from, so a consumer's update-check workflow
# (templates/update-check.yml) has something to compare against without
# needing to diff file contents itself. Best-effort: a shallow clone of a
# tag describes as that tag; a full clone of main with no exact tag match
# falls back to a short SHA rather than failing.
VERSION="$(cd "$SRC_DIR" && git describe --tags --always 2>/dev/null || echo unknown)"
if [[ ! -f "$TARGET/.craft-gate-version" ]] || [[ "$(cat "$TARGET/.craft-gate-version")" != "$VERSION" ]]; then
  echo "$VERSION" > "$TARGET/.craft-gate-version"
fi

echo "✓ copied CRAFTSMANSHIP.md, catalog.yaml, scripts/, .claude/skills/tidy-first/"
echo "  now on craft-gate $VERSION"
echo
echo "Manual steps left — these touch files that differ per repo, so they're"
echo "not auto-merged: the pre-push hook, the CI jobs, the AGENTS.md section,"
echo "and a few optional workflows. They're listed, with the commands, in:"
echo "  $SRC_DIR/INSTALL.md"
echo
echo "Re-run this script any time to pull the latest catalog/scripts."
