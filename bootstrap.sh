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
# scripts/check_tidy_ratchet.sh, scripts/report_tidy_history.sh,
# scripts/craftcov.py, scripts/check_refactor_first.py,
# scripts/check_complexity_ratchet.py, scripts/craftcov_pr_comment.py,
# .claude/skills/tidy-first/SKILL.md, and
# .craft-gate-version (a plain-text marker of which release this checkout
# came from — see templates/update-check.yml, which reads it to detect
# drift). It never edits CLAUDE.md, .pre-commit-config.yaml, or your CI
# workflow — those vary too much per project to auto-merge safely; it prints
# what to add and where instead. Safe to re-run any time to pull an update.
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
copy_file "$SRC_DIR/scripts/craftcov.py" "$TARGET/scripts/craftcov.py"
copy_file "$SRC_DIR/scripts/check_refactor_first.py" "$TARGET/scripts/check_refactor_first.py"
copy_file "$SRC_DIR/scripts/check_complexity_ratchet.py" "$TARGET/scripts/check_complexity_ratchet.py"
copy_file "$SRC_DIR/scripts/craftcov_pr_comment.py" "$TARGET/scripts/craftcov_pr_comment.py"
chmod +x "$TARGET/scripts/check_tidy_ratchet.sh" "$TARGET/scripts/report_tidy_history.sh" \
  "$TARGET/scripts/craftcov.py" "$TARGET/scripts/check_refactor_first.py" \
  "$TARGET/scripts/check_complexity_ratchet.py" "$TARGET/scripts/craftcov_pr_comment.py"
copy_file "$SRC_DIR/skills/tidy-first/SKILL.md" "$TARGET/.claude/skills/tidy-first/SKILL.md"

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
echo "not auto-merged:"
echo
echo "  1. Wire the ratchet into your local pre-push hook:"
echo "       cat '$SRC_DIR/templates/pre-commit-hook.yaml'"
echo "     Merge its 'local' repo block into .pre-commit-config.yaml"
echo "     (or use it as your starting file if you don't have one yet),"
echo "     then: prek install --hook-type pre-push"
echo
echo "  2. Wire all three default CI gates — the ratchet, Refactor First,"
echo "     and the complexity ratchet — plus, optionally, two reporting jobs"
echo "     (a sticky PR comment and a GitHub code-scanning SARIF upload —"
echo "     neither is a gate, and the SARIF one needs a public repo or"
echo "     GitHub Advanced Security):"
echo "       cat '$SRC_DIR/templates/ci-job.yml'"
echo "     Add the job(s) you want to .github/workflows/ci.yml, set your branch name."
echo "     Refactor First needs craftCov's own tools on top: add a 'craftcov'"
echo "     extra (ruff/pylint/vulture — pyyaml too, unless already a dependency)"
echo "     to your dependency file. The complexity ratchet needs its own"
echo "     'complexity' extra (radon, cognitive-complexity). See README's"
echo "     craftCov and 'The complexity ratchet' sections for the exact"
echo "     versions this release expects."
echo
echo "  3. Add the Tidy First section to CLAUDE.md:"
echo "       cat '$SRC_DIR/templates/CLAUDE.md.snippet.md'"
echo "     Append it to your project's CLAUDE.md (or create one)."
echo
echo "     Optional, not a craftsmanship gate (skip if you don't want"
echo "     test-first/BDD mandated for every feature):"
echo "       cat '$SRC_DIR/templates/tdd-bdd-yagni.snippet.md'"
echo "     A TDD+BDD+YAGNI workflow section for CLAUDE.md."
echo
echo "  4. Stop needing to remember to re-run this:"
echo "       cp '$SRC_DIR/templates/update-check.yml' .github/workflows/craft-gate-update.yml"
echo "     Weekly workflow that checks for a new craft-gate release and opens"
echo "     a PR with the diff if there is one. No new credentials needed."
echo
echo "Re-run this script any time to pull the latest catalog/scripts."
