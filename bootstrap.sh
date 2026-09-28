#!/usr/bin/env bash
# Install or update craft-gate in a target repo.
#
# Usage:
#   bash bootstrap.sh [target-dir]      # default target: current directory
#
# Run this from inside a checkout of craft-gate itself (clone a tagged
# release rather than piping this over the network — see README.md):
#   git clone --branch v0.1.0 --depth 1 https://github.com/<you>/craft-gate /tmp/craft-gate
#   bash /tmp/craft-gate/bootstrap.sh ~/code/my-project
#
# Only touches files this tool fully owns — CRAFTSMANSHIP.md, catalog.yaml,
# scripts/check_tidy_ratchet.sh, scripts/report_tidy_history.sh, and
# .claude/skills/tidy-first/SKILL.md. It never edits CLAUDE.md,
# .pre-commit-config.yaml, or your CI workflow — those vary too much per
# project to auto-merge safely; it prints what to add and where instead.
# Safe to re-run any time to pull an update.
set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${1:-.}"

if [[ ! -d "$TARGET/.git" ]]; then
  echo "✗ '$TARGET' doesn't look like a git repo root (no .git/ found)." >&2
  exit 1
fi

echo "Installing/updating craft-gate in $TARGET ..."

mkdir -p "$TARGET/scripts" "$TARGET/.claude/skills/tidy-first"

# Plain `cp` refuses when src and dst resolve to the literal same file — true
# whenever this runs against craft-gate's own checkout (self-application) and
# possible for any target already fully up to date. Compare content instead
# of paths: skip only when the bytes already match, so both cases work and a
# genuine update still copies.
copy_file() {
  local src="$1" dst="$2"
  if [[ -f "$dst" ]] && cmp -s "$src" "$dst"; then
    return 0
  fi
  cp "$src" "$dst"
}

copy_file "$SRC_DIR/CRAFTSMANSHIP.md" "$TARGET/CRAFTSMANSHIP.md"
copy_file "$SRC_DIR/catalog.yaml" "$TARGET/catalog.yaml"
copy_file "$SRC_DIR/scripts/check_tidy_ratchet.sh" "$TARGET/scripts/check_tidy_ratchet.sh"
copy_file "$SRC_DIR/scripts/report_tidy_history.sh" "$TARGET/scripts/report_tidy_history.sh"
chmod +x "$TARGET/scripts/check_tidy_ratchet.sh" "$TARGET/scripts/report_tidy_history.sh"
copy_file "$SRC_DIR/skills/tidy-first/SKILL.md" "$TARGET/.claude/skills/tidy-first/SKILL.md"

echo "✓ copied CRAFTSMANSHIP.md, catalog.yaml, scripts/, .claude/skills/tidy-first/"
echo
echo "Manual steps left — these touch files that differ per repo, so they're"
echo "not auto-merged:"
echo
echo "  1. Wire the ratchet into your local pre-push hook:"
echo "       cat '$SRC_DIR/templates/pre-commit-hook.yaml'"
echo "     Merge its 'local' repo block into .pre-commit-config.yaml"
echo "     (or use it as your starting file if you don't have one yet),"
echo "     then: prek install --hook-type pre-push"
echo
echo "  2. Wire the ratchet into CI:"
echo "       cat '$SRC_DIR/templates/ci-job.yml'"
echo "     Add that job to .github/workflows/ci.yml, set your branch name."
echo
echo "  3. Add the Tidy First section to CLAUDE.md:"
echo "       cat '$SRC_DIR/templates/CLAUDE.md.snippet.md'"
echo "     Append it to your project's CLAUDE.md (or create one)."
echo
echo "Re-run this script any time to pull the latest catalog/scripts."
