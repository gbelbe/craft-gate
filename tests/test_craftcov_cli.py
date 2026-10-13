#!/usr/bin/env python3
"""Characterization of the craftcov CLI end to end (no pytest dependency).

Runs scripts/craftcov.py as a subprocess, with the real ruff / pylint / vulture, against a
throwaway git repo built from tests/fixtures/. Pins the observable contract — report text,
JSON/SARIF shape, caching, the changes-since-last-run snapshot, --file scoping — so the
module can be restructured under it. Needs the craftcov extra: `uv run --extra dev ...`.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "craftcov.py"
FIXTURES = ROOT / "tests" / "fixtures"
ENV = {**os.environ, "PATH": f"{Path(sys.executable).parent}{os.pathsep}{os.environ['PATH']}"}

ELSE_AFTER_RETURN = "def f(x):\n    if x:\n        return 1\n    else:\n        return 2\n"
DUP_BODY = "".join(f"        value_{i} = {i} * 2\n" for i in range(10))


class Repo:
    """A tmp git repo holding copies of some fixtures, with its own cache/snapshot files."""

    def __init__(self, tmp: str, fixtures: tuple[str, ...]) -> None:
        self.root = Path(tmp).resolve()
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        for name in fixtures:
            (self.root / name).write_text((FIXTURES / name).read_text())
        self.add_all()

    def add_all(self) -> None:
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True)

    def run(self, *args: str, state: bool = True) -> subprocess.CompletedProcess:
        # the cache/snapshot live outside the scanned tree so they never count as files
        extra = ["--cache-file", str(self.cache), "--snapshot-file", str(self.snapshot)]
        cmd = [
            sys.executable,
            str(SCRIPT),
            "--path",
            str(self.root),
            *(extra if state else []),
            *args,
        ]
        return subprocess.run(cmd, capture_output=True, text=True, env=ENV, check=False)

    def json(self, *args: str) -> dict:
        proc = self.run("--format", "json", *args)
        assert proc.returncode == 0, proc.stderr
        return json.loads(proc.stdout)

    @property
    def cache(self) -> Path:
        return self.root.parent / f"{self.root.name}-cache.json"

    @property
    def snapshot(self) -> Path:
        return self.root.parent / f"{self.root.name}-snapshot.json"


def normalized(text: str) -> str:
    text = re.sub(r"in \d+\.\d\ds", "in Ns", text)
    text = re.sub(r"pass: \d+\.\d\ds", "pass: Ns", text)
    return re.sub(r"\(\d{4}-\d\d-\d\dT[\d:]+Z\)", "(TS)", text)


def with_repo(*fixtures: str):
    def decorate(fn):
        def wrapper() -> None:
            with tempfile.TemporaryDirectory() as tmp:
                fn(Repo(tmp, fixtures))

        wrapper.__name__ = fn.__name__
        return wrapper

    return decorate


SMELLY = ("guard_clauses.py", "clean.py", "dead_code.py")
SMELLY_TOTAL = 6  # 5 dead-code in dead_code.py + 1 guard-clauses in guard_clauses.py
DEAD_CODE_FINDINGS = 5
M_PY_TOTAL = 6  # m.py: per class, 1 guard-clauses + 2 vulture dead-code methods
DUP_LINES = 11  # the shared `def run` line plus its ten-line body
CATALOG_ENTRIES = 35
DETECTABLE_ENTRIES = 8

FIRST_RUN = """craftCov — craftsmanship heuristic scan
Scanned 3 files (3 changed, 0 from cache) in Ns
Duplicate-code pass: Ns (always full-corpus — see DESIGN.md)

Changes since last run: none — this is the first run (no previous snapshot).

By heuristic
CODE    ID                                      COUNT  SOURCE
CG002   dead-code                                   5  Kent Beck, Tidy First? (2023)
CG001   guard-clauses                               1  Kent Beck, Tidy First? (2023)
        TOTAL                                       6

By file (top 15)
      5  dead_code.py
      1  guard_clauses.py

By class (top 15, module-level findings excluded)

By library (top-level directory)
      6  (root)

Every finding
  dead_code.py:7  CG002 dead-code (ruff:F401)
  dead_code.py:10  CG002 dead-code (vulture 60%)
  dead_code.py:11  CG002 dead-code (ruff:F841)
  dead_code.py:15  CG002 dead-code (ruff:F811)
  dead_code.py:19  CG002 dead-code (vulture 60%)
  guard_clauses.py:10  CG001 guard-clauses (ruff:RET505)
"""


@with_repo(*SMELLY)
def test_first_text_run_report_is_pinned_line_for_line(repo: Repo) -> None:
    proc = repo.run("--verbose")

    assert proc.returncode == 0, proc.stderr
    out = normalized(proc.stdout)
    assert out.startswith(FIRST_RUN)
    assert out.endswith(
        "\n8/35 heuristics have an automatic detector (22%) — the rest need the procedure in "
        "CRAFTSMANSHIP.md (ask the developer), not a scan. Run with --list-detectors to see "
        "which is which.\n"
    )


@with_repo(*SMELLY)
def test_without_verbose_the_per_finding_list_is_omitted(repo: Repo) -> None:
    out = repo.run().stdout
    assert "By heuristic" in out
    assert "Every finding" not in out


@with_repo("clean.py")
def test_a_clean_tree_says_so_and_prints_no_tables(repo: Repo) -> None:
    out = normalized(repo.run().stdout)
    assert "No findings for the detectable heuristics. ✓" in out
    assert "By heuristic" not in out
    assert "Every finding" not in repo.run("--verbose").stdout


@with_repo(*SMELLY)
def test_json_carries_summary_findings_timing_and_scope(repo: Repo) -> None:
    doc = repo.json()

    assert set(doc) == {"summary", "findings", "timing", "scope", "diff"}
    assert doc["scope"] is None
    assert doc["summary"]["total"] == SMELLY_TOTAL
    assert doc["summary"]["by_heuristic"] == {"dead-code": 5, "guard-clauses": 1}
    assert sorted(doc["findings"]) == ["clean.py", "dead_code.py", "guard_clauses.py"]
    assert doc["findings"]["clean.py"] == []
    first = doc["findings"]["guard_clauses.py"][0]
    assert first == {
        "line": 10,
        "col": first["col"],
        "tool": "ruff",
        "rule": "RET505",
        "confidence": None,
        "heuristic_id": "guard-clauses",
        "heuristic_code": "CG001",
        "class": None,
    }
    vulture = [f for f in doc["findings"]["dead_code.py"] if f["tool"] == "vulture"]
    assert [f["confidence"] for f in vulture] == [60, 60]
    assert set(doc["timing"]) == {"total_files", "changed", "cached", "elapsed", "dupes_elapsed"}
    assert (doc["timing"]["total_files"], doc["timing"]["changed"]) == (3, 3)


@with_repo(*SMELLY)
def test_json_diff_section_appears_only_when_diffing(repo: Repo) -> None:
    first = repo.json()["diff"]
    assert first["previous_generated_at"] is None  # nothing to compare against yet
    assert {c["heuristic_id"]: (c["old"], c["new"]) for c in first["by_heuristic"]} == {
        "dead-code": (0, 5),
        "guard-clauses": (0, 1),
    }

    (repo.root / "extra.py").write_text(ELSE_AFTER_RETURN)
    repo.add_all()
    second = repo.json()
    assert second["diff"]["previous_generated_at"].endswith("Z")
    moved = {c["heuristic_id"]: (c["old"], c["new"]) for c in second["diff"]["by_heuristic"]}
    assert moved["guard-clauses"] == (1, 2)
    assert "dead-code" not in moved or moved["dead-code"][0] == DEAD_CODE_FINDINGS

    assert "diff" not in repo.json("--no-diff")


@with_repo(*SMELLY)
def test_second_run_is_served_from_cache_until_a_file_changes(repo: Repo) -> None:
    assert repo.json()["timing"]["cached"] == 0
    warm = repo.json()["timing"]
    assert (warm["changed"], warm["cached"]) == (0, 3)

    (repo.root / "clean.py").write_text((repo.root / "clean.py").read_text() + "\nZ = 1\n")
    edited = repo.json()["timing"]
    assert (edited["changed"], edited["cached"]) == (1, 2)

    cold = repo.json("--no-cache")["timing"]
    assert (cold["changed"], cold["cached"]) == (3, 0)


@with_repo(*SMELLY)
def test_cache_drops_entries_for_deleted_files(repo: Repo) -> None:
    repo.run()
    assert "dead_code.py" in json.loads(repo.cache.read_text())["files"]

    (repo.root / "dead_code.py").unlink()
    repo.add_all()
    repo.run()
    assert sorted(json.loads(repo.cache.read_text())["files"]) == ["clean.py", "guard_clauses.py"]


@with_repo(*SMELLY)
def test_changes_since_last_run_reports_new_resolved_and_totals(repo: Repo) -> None:
    repo.run()
    same = normalized(repo.run().stdout)
    assert "Changes since last run (TS): none — identical totals." in same

    (repo.root / "dead_code.py").unlink()
    (repo.root / "again.py").write_text(ELSE_AFTER_RETURN)
    repo.add_all()
    changed = normalized(repo.run().stdout)

    assert "Changes since last run (TS)\n" in changed
    assert "  CG002   dead-code                                  5 -> 1     (-4)" in changed
    assert "  CG001   guard-clauses                              1 -> 2     (+1)" in changed
    assert "          TOTAL                                      6 -> 3     (-3)" in changed

    (repo.root / "again.py").unlink()
    (repo.root / "dead_code.py").write_text("import os\n")  # nothing but an unused import
    (repo.root / "guard_clauses.py").unlink()
    (repo.root / "const.py").write_text((FIXTURES / "explaining_constant.py").read_text())
    repo.add_all()
    tagged = normalized(repo.run().stdout)

    assert "(RESOLVED)" in tagged  # guard-clauses is gone entirely
    assert "(NEW)" in tagged  # explaining-constant was never there before


@with_repo(*SMELLY)
def test_no_diff_hides_the_section_but_the_snapshot_still_updates(repo: Repo) -> None:
    out = repo.run("--no-diff").stdout
    assert "Changes since last run" not in out
    snap = json.loads(repo.snapshot.read_text())
    assert snap["total"] == SMELLY_TOTAL
    assert snap["by_heuristic"] == {"dead-code": 5, "guard-clauses": 1}


@with_repo(*SMELLY)
def test_file_scope_filters_the_report_and_leaves_the_snapshot_alone(repo: Repo) -> None:
    repo.run()
    before = repo.snapshot.read_text()

    doc = repo.json("--file", "dead_code.py")
    assert doc["scope"] == "dead_code.py"
    assert list(doc["findings"]) == ["dead_code.py"]
    assert doc["summary"]["total"] == DEAD_CODE_FINDINGS
    assert "diff" not in doc

    text = normalized(repo.run("--file", str(repo.root / "guard_clauses.py")).stdout)
    assert "Reporting scope: guard_clauses.py only (full corpus was still scanned" in text
    assert "Changes since last run" not in text
    assert repo.snapshot.read_text() == before


@with_repo(*SMELLY)
def test_file_scope_rejects_a_file_git_does_not_track(repo: Repo) -> None:
    proc = repo.run("--file", "nope.py")
    assert proc.returncode != 0
    assert "--file 'nope.py' not found among this repo's tracked .py files" in proc.stderr


@with_repo()
def test_class_filter_keeps_only_that_classes_findings(repo: Repo) -> None:
    (repo.root / "m.py").write_text(
        "class A:\n    def f(self, x):\n        if x:\n            return 1\n        else:\n"
        "            return 2\n\n\nclass B:\n    def g(self, x):\n        if x:\n"
        "            return 1\n        else:\n            return 2\n"
    )
    repo.add_all()

    everything = repo.json("--file", "m.py")["summary"]["by_class"]
    assert everything == {"m.py::A": 3, "m.py::B": 3}
    only_b = repo.json("--file", "m.py", "--class", "B")
    assert only_b["scope"] == "m.py::B"
    assert only_b["summary"]["by_class"] == {"m.py::B": 3}
    assert repo.json("--class", "B")["summary"]["total"] == M_PY_TOTAL  # ignored without --file


@with_repo()
def test_duplicate_code_is_reported_on_both_sides_and_never_cached(repo: Repo) -> None:
    for name in ("one.py", "two.py"):
        (repo.root / name).write_text(f"class {name[:3].title()}:\n    def run(self):\n{DUP_BODY}")
    repo.add_all()

    doc = repo.json()
    ids = set(doc["summary"]["by_heuristic"])
    assert "consolidate-duplicate-conditional" in ids
    one = [f for f in doc["findings"]["one.py"] if f["tool"] == "dupes"]
    assert one[0]["duplicate_of"] == "two.py:2-12"
    assert one[0]["dup_lines"] == DUP_LINES
    assert one[0]["class"] == "One"
    cached = json.loads(repo.cache.read_text())["files"]["one.py"]["findings"]
    assert all(f["tool"] != "dupes" for f in cached)
    verbose = repo.run("--verbose").stdout
    assert "<-> two.py:2-12 (11 lines)" in verbose
    assert "(dupes)" in verbose


@with_repo(*SMELLY)
def test_sarif_output_is_a_valid_document_with_one_result_per_finding(repo: Repo) -> None:
    proc = repo.run("--format", "sarif")
    doc = json.loads(proc.stdout)

    assert doc["version"] == "2.1.0"
    results = doc["runs"][0]["results"]
    assert len(results) == SMELLY_TOTAL
    assert {r["ruleId"] for r in results} == {"dead-code", "guard-clauses"}
    assert len(doc["runs"][0]["tool"]["driver"]["rules"]) == DETECTABLE_ENTRIES


def test_list_detectors_prints_one_line_per_catalog_entry() -> None:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--list-detectors"],
        capture_output=True,
        text=True,
        env=ENV,
        check=False,
    )
    lines = proc.stdout.splitlines()

    assert proc.returncode == 0
    assert len(lines) == CATALOG_ENTRIES
    assert lines[0].startswith("CG001   guard-clauses")
    assert sum(1 for line in lines if "needs judgment" not in line) == DETECTABLE_ENTRIES


@with_repo(*SMELLY)
def test_vulture_confidence_floor_filters_its_findings(repo: Repo) -> None:
    low = repo.json("--no-cache")["summary"]["by_heuristic"]["dead-code"]
    high = repo.json("--no-cache", "--vulture-min-confidence", "100")["summary"]["by_heuristic"]
    assert (low, high["dead-code"]) == (5, 3)  # the two 60% vulture findings drop out


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
    print(f"craftcov CLI characterization passed ({len(tests)})")
