#!/usr/bin/env python3
"""Ground-truth regression test for craftCov's detectors.

Not pytest — this project deliberately has no test-framework dependency
(see README's Requirements: PyYAML + whichever detector tools you use, and
nothing else). Runs craftcov.py against tests/fixtures/ (one small,
hand-authored file per detectable heuristic, each with a docstring
explaining exactly what it's supposed to trigger and why) and checks that
each detector fires where it should.

Presence checks, not exact-match: a fixture built to trigger one heuristic
often legitimately trips others too (replace_conditional_with_polymorphism.py
also trips guard-clauses and explaining-constant — that's the fixture being
honest about how real code behaves, not a bug to suppress). The one file
held to an exact-zero standard is clean.py, the negative control.

Usage:
    python3 tests/test_fixtures.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"

# file -> heuristic_id(s) that MUST appear somewhere in that file's findings
EXPECTED: dict[str, set[str]] = {
    "guard_clauses.py": {"guard-clauses"},
    "dead_code.py": {"dead-code"},
    "explaining_constant.py": {"explaining-constant"},
    "extract_helper.py": {"extract-helper"},
    "extract_class.py": {"extract-class"},
    "introduce_parameter_object.py": {"introduce-parameter-object"},
    "replace_conditional_with_polymorphism.py": {"replace-conditional-with-polymorphism"},
    "consolidate_duplicate_conditional_a.py": {"consolidate-duplicate-conditional"},
    "consolidate_duplicate_conditional_b.py": {"consolidate-duplicate-conditional"},
}
# held to zero findings, not just "at least these"
MUST_BE_CLEAN = {"clean.py"}


def main() -> int:
    cache = ROOT / ".craftcov_cache.json.fixtures_test"
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "craftcov.py"), "--path", str(FIXTURES), "--cache-file", str(cache), "--no-cache", "--format", "json"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    cache.unlink(missing_ok=True)
    if proc.returncode != 0:
        print(f"✗ craftcov.py exited {proc.returncode}:\n{proc.stderr}", file=sys.stderr)
        return 1

    data = json.loads(proc.stdout)
    findings = data["findings"]

    failures: list[str] = []

    for rel, expected_ids in EXPECTED.items():
        found_ids = {f["heuristic_id"] for f in findings.get(rel, [])}
        missing = expected_ids - found_ids
        if missing:
            failures.append(f"{rel}: expected {sorted(missing)}, got {sorted(found_ids) or '(nothing)'}")

    for rel in MUST_BE_CLEAN:
        found = findings.get(rel, [])
        if found:
            ids = sorted({f["heuristic_id"] for f in found})
            failures.append(f"{rel}: expected zero findings (negative control), got {ids}")

    all_fixture_files = {p.name for p in FIXTURES.glob("*.py")}
    unaccounted = all_fixture_files - set(EXPECTED) - MUST_BE_CLEAN
    if unaccounted:
        failures.append(f"fixtures present but not listed in EXPECTED or MUST_BE_CLEAN: {sorted(unaccounted)}")

    if failures:
        print("✗ ground-truth regression failed:")
        for f in failures:
            print(f"  - {f}")
        return 1

    print(f"✓ all {len(EXPECTED)} detectors fired on their ground-truth fixture, clean.py stayed clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
