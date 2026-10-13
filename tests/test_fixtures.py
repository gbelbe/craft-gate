"""Ground-truth regression test for craftCov's detectors.

Runs craftcov.py against tests/fixtures/ (one small, hand-authored file per detectable heuristic,
each with a docstring explaining exactly what it's supposed to trigger and why) and checks that
each detector fires where it should.

Presence checks, not exact-match: a fixture built to trigger one heuristic often legitimately
trips others too (replace_conditional_with_polymorphism.py also trips guard-clauses and
explaining-constant — that's the fixture being honest about how real code behaves, not a bug to
suppress). The one file held to an exact-zero standard is clean.py, the negative control.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

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


@pytest.fixture(scope="module")
def findings(tmp_path_factory: pytest.TempPathFactory) -> dict[str, list[dict]]:
    scratch = tmp_path_factory.mktemp("fixtures-scan")
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "craftcov.py"),
            "--path",
            str(FIXTURES),
            "--cache-file",
            str(scratch / "cache.json"),
            "--snapshot-file",
            str(scratch / "snapshot.json"),
            "--no-cache",
            "--no-diff",
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)["findings"]


@pytest.mark.parametrize(("rel", "expected_ids"), sorted(EXPECTED.items()))
def test_each_detector_fires_on_its_ground_truth_fixture(findings, rel, expected_ids) -> None:
    found_ids = {f["heuristic_id"] for f in findings.get(rel, [])}

    assert expected_ids <= found_ids, f"{rel}: got {sorted(found_ids) or '(nothing)'}"


@pytest.mark.parametrize("rel", sorted(MUST_BE_CLEAN))
def test_the_negative_control_stays_clean(findings, rel) -> None:
    ids = sorted({f["heuristic_id"] for f in findings.get(rel, [])})

    assert ids == []


def test_every_fixture_file_is_accounted_for() -> None:
    on_disk = {p.name for p in FIXTURES.glob("*.py")}

    assert on_disk == set(EXPECTED) | MUST_BE_CLEAN
