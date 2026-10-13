#!/usr/bin/env python3
"""Characterization of craftcov's pure pieces (no pytest dependency, no external tools).

Pins what the module does today so it can be restructured under it: the
dupes engine, scope attribution, detector indexing, aggregation, the cache and
snapshot files, the SARIF document, and discovery. Needs only PyYAML. The
end-to-end behaviour (real ruff/pylint/vulture) is in test_craftcov_cli.py.
"""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import craftcov  # noqa: E402


def raises_exit(fn, *args) -> str:
    try:
        fn(*args)
    except SystemExit as exc:
        return str(exc)
    raise AssertionError("expected SystemExit")


# -- dupes: line normalisation -----------------------------------------------------


def test_strip_lines_drops_comments_blanks_and_imports_keeping_line_numbers() -> None:
    source = (
        "import os\n"
        "from typing import (\n"
        "    Any,\n"
        ")\n"
        "\n"
        "# a comment\n"
        "x = 1  # trailing\n"
        "s = '# not a comment'\n"
        "def f():\n"
        "    import sys\n"
        "    return x\n"
    )
    assert craftcov.strip_lines_for_dupes(source) == [
        (7, "x = 1"),
        (8, "s = '# not a comment'"),
        (9, "def f():"),
        (11, "return x"),
    ]


def test_strip_lines_survives_a_file_the_tokenizer_cannot_read() -> None:
    # an unterminated bracket makes tokenize raise TokenError; the scan must carry on
    assert craftcov.strip_lines_for_dupes("x = (1,\n  2\n") == [(1, "x = (1,"), (2, "2")]


# -- dupes: block matching ---------------------------------------------------------


def numbered(texts: list[str]) -> list[tuple[int, str]]:
    return [(i, t) for i, t in enumerate(texts, start=1)]


def test_a_shared_block_is_reported_once_with_its_true_length() -> None:
    shared = [f"line {i}" for i in range(20)]
    files = {"a.py": numbered(["a-only", *shared, "a-end"]), "b.py": numbered([*shared, "b-end"])}

    assert craftcov.find_duplicate_blocks(files, min_lines=4) == [
        {
            "file_a": "a.py",
            "start_a": 2,
            "end_a": 21,
            "file_b": "b.py",
            "start_b": 1,
            "end_b": 20,
            "lines": 20,
        }
    ]


def test_min_lines_is_inclusive_at_the_boundary() -> None:
    block = ["p", "q", "r"]
    files = {"a.py": numbered([*block, "x"]), "b.py": numbered(["y", *block])}

    assert len(craftcov.find_duplicate_blocks(files, min_lines=3)) == 1
    assert craftcov.find_duplicate_blocks(files, min_lines=4) == []


def test_a_block_repeated_inside_one_file_is_found() -> None:
    texts = ["a", "b", "c", "mid", "a", "b", "c"]
    found = craftcov.find_duplicate_blocks({"a.py": numbered(texts)}, min_lines=3)

    assert [(b["start_a"], b["start_b"], b["lines"]) for b in found] == [(1, 5, 3)]


def test_no_duplicates_means_no_blocks() -> None:
    files = {"a.py": numbered(["1", "2", "3", "4"]), "b.py": numbered(["5", "6", "7", "8"])}
    assert craftcov.find_duplicate_blocks(files, min_lines=2) == []
    assert craftcov.find_duplicate_blocks({}, min_lines=2) == []


def test_run_dupes_reports_both_halves_of_a_pair() -> None:
    body = "".join(f"    y{i} = {i}\n" for i in range(6))
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "a.py").write_text(f"def f():\n{body}")
        (root / "b.py").write_text(f"x = 0\n\ndef g():\n{body}")
        items = craftcov.run_dupes(root, ["a.py", "b.py"], min_lines=5)

    assert items == [
        {
            "rel": "a.py",
            "line": 2,
            "col": 0,
            "tool": "dupes",
            "rule": None,
            "duplicate_of": "b.py:4-9",
            "dup_lines": 6,
        },
        {
            "rel": "b.py",
            "line": 4,
            "col": 0,
            "tool": "dupes",
            "rule": None,
            "duplicate_of": "a.py:2-7",
            "dup_lines": 6,
        },
    ]


# -- scope attribution -------------------------------------------------------------


NESTED = (
    "def top():\n"  # 1
    "    pass\n"  # 2
    "class Outer:\n"  # 3
    "    def m(self):\n"  # 4
    "        pass\n"  # 5
    "    class Inner:\n"  # 6
    "        def n(self):\n"  # 7
    "            pass\n"  # 8
    "x = 1\n"  # 9
)


def test_scope_index_qualifies_names_and_marks_kinds() -> None:
    assert sorted(craftcov.build_scope_index(NESTED)) == [
        (1, 2, "function", "top"),
        (3, 8, "class", "Outer"),
        (4, 5, "function", "Outer.m"),
        (6, 8, "class", "Outer.Inner"),
        (7, 8, "function", "Outer.Inner.n"),
    ]


def test_enclosing_class_picks_the_innermost_class_and_none_outside() -> None:
    scopes = craftcov.build_scope_index(NESTED)
    assert craftcov.enclosing_class(scopes, 5) == "Outer"
    assert craftcov.enclosing_class(scopes, 8) == "Outer.Inner"
    assert craftcov.enclosing_class(scopes, 2) is None  # a top-level function
    assert craftcov.enclosing_class(scopes, 9) is None
    assert craftcov.enclosing_class([], 1) is None


def test_scope_index_of_a_syntax_error_is_empty() -> None:
    assert craftcov.build_scope_index("def (:\n") == []


# -- detector indexing -------------------------------------------------------------


def test_the_real_catalog_indexes_cleanly() -> None:
    catalog = craftcov.load_catalog()
    rule_maps, whole_tool, corpus_tool = craftcov.build_detector_index(catalog)

    assert set(rule_maps) == {"ruff", "pylint"}
    assert set(whole_tool) == {"vulture"}
    assert set(corpus_tool) == {"dupes"}
    assert rule_maps["pylint"]["R0902"]["id"] == "extract-class"
    assert corpus_tool["dupes"]["entry"]["id"] == "consolidate-duplicate-conditional"
    assert "tool" not in corpus_tool["dupes"]


def test_collisions_and_unknown_tools_are_authoring_errors() -> None:
    def entry(id_: str, *detectors: dict) -> dict:
        return {"id": id_, "detectors": list(detectors)}

    ruff = {"tool": "ruff", "rules": ["E1"]}
    msg = raises_exit(craftcov.build_detector_index, [entry("a", ruff), entry("b", ruff)])
    assert "ruff rule E1 is claimed by both a and b" in msg

    vulture = {"tool": "vulture"}
    msg = raises_exit(craftcov.build_detector_index, [entry("a", vulture), entry("b", vulture)])
    assert "vulture (a whole-file detector) is claimed by both a and b" in msg

    dupes = {"tool": "dupes", "min_lines": 3}
    msg = raises_exit(craftcov.build_detector_index, [entry("a", dupes), entry("b", dupes)])
    assert "dupes (a corpus-wide detector) is claimed by both a and b" in msg

    msg = raises_exit(craftcov.build_detector_index, [entry("a", {"tool": "mystery"})])
    assert "unknown detector tool 'mystery' on a" in msg


def test_entries_without_detectors_are_ignored_and_dupes_config_is_kept() -> None:
    catalog = [{"id": "plain"}, {"id": "d", "detectors": [{"tool": "dupes", "min_lines": 3}]}]
    rule_maps, whole_tool, corpus_tool = craftcov.build_detector_index(catalog)

    assert (rule_maps, whole_tool) == ({}, {})
    assert corpus_tool == {"dupes": {"entry": catalog[1], "min_lines": 3}}


# -- aggregation and diffing -------------------------------------------------------


def finding(hid: str, cls: str | None = None, line: int = 1) -> dict:
    return {"heuristic_id": hid, "class": cls, "line": line}


def test_aggregate_groups_by_heuristic_file_class_and_top_directory() -> None:
    by_file = {
        "pkg/a.py": [finding("x", "A"), finding("x", "A"), finding("y")],
        "top.py": [finding("x")],
        "pkg/clean.py": [],
    }

    assert craftcov.aggregate(by_file) == {
        "total": 4,
        "by_heuristic": {"x": 3, "y": 1},
        "by_file": {"pkg/a.py": 3, "top.py": 1},
        "by_class": {"pkg/a.py::A": 2, "pkg/a.py": 1, "top.py": 1},
        "by_library": {"pkg": 3, "(root)": 1},
    }


def test_aggregate_of_nothing_is_all_zero() -> None:
    assert craftcov.aggregate({}) == {
        "total": 0,
        "by_heuristic": {},
        "by_file": {},
        "by_class": {},
        "by_library": {},
    }


def test_diff_by_heuristic_reports_changes_largest_first() -> None:
    old = {"gone": 2, "same": 3, "grew": 1, "shrank": 9}
    new = {"same": 3, "grew": 2, "shrank": 4, "fresh": 3}

    assert craftcov.diff_by_heuristic(old, new) == [
        ("shrank", 9, 4),
        ("fresh", 0, 3),
        ("gone", 2, 0),
        ("grew", 1, 2),
    ]


def test_diff_against_no_snapshot_lists_everything_as_new() -> None:
    assert craftcov.diff_by_heuristic(None, {"a": 2}) == [("a", 0, 2)]
    assert craftcov.diff_by_heuristic({"a": 2}, {"a": 2}) == []


# -- cache and snapshot files ------------------------------------------------------


def test_cache_round_trips_and_every_bad_state_means_start_fresh() -> None:
    fresh = {"version": craftcov.CACHE_VERSION, "files": {}}
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "cache.json"
        assert craftcov.load_cache(path) == fresh  # missing

        path.write_text("{not json")
        assert craftcov.load_cache(path) == fresh  # corrupt

        path.write_text(json.dumps({"version": craftcov.CACHE_VERSION - 1, "files": {"a": 1}}))
        assert craftcov.load_cache(path) == fresh  # schema changed

        data = {"version": craftcov.CACHE_VERSION, "files": {"a.py": {"hash": "h", "findings": []}}}
        craftcov.save_cache(path, data)
        assert craftcov.load_cache(path) == data


def test_snapshot_round_trips_only_the_totals_and_rejects_bad_files() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "snap.json"
        assert craftcov.load_report_snapshot(path) is None

        path.write_text("nope")
        assert craftcov.load_report_snapshot(path) is None

        path.write_text(json.dumps({"total": 3}))
        assert craftcov.load_report_snapshot(path) is None  # no by_heuristic

        agg = {"total": 3, "by_heuristic": {"x": 3}, "by_file": {"a.py": 3}}
        craftcov.save_report_snapshot(path, agg)
        snap = craftcov.load_report_snapshot(path)
        assert snap is not None
        assert (snap["total"], snap["by_heuristic"]) == (3, {"x": 3})
        assert "by_file" not in snap
        assert snap["generated_at"].endswith("Z")


# -- SARIF and detector listing ----------------------------------------------------


CATALOG = [
    {"id": "dead", "code": "CG1", "name": "Dead", "smell": "unused", "action": "delete",
     "detectors": [{"tool": "ruff", "rules": ["F401", "F841"]}, {"tool": "vulture"}]},
    {"id": "judge", "code": "CG2", "name": "Judge"},
    {"id": "dup", "code": "CG3", "name": "Dup", "detectors": [{"tool": "dupes"}]},
]  # fmt: skip


def test_sarif_lists_every_detectable_rule_and_one_result_per_finding() -> None:
    by_file = {
        "b.py": [{"heuristic_id": "dead", "heuristic_code": "CG1", "line": 0}],
        "a.py": [{"heuristic_id": "dup", "heuristic_code": "CG3", "line": 7}],
    }
    doc = craftcov.format_sarif(by_file, CATALOG)

    assert doc["version"] == "2.1.0"
    run = doc["runs"][0]
    assert run["tool"]["driver"]["name"] == "craftCov"
    rules = run["tool"]["driver"]["rules"]
    assert [r["id"] for r in rules] == ["dead", "dup"]
    assert rules[0]["shortDescription"] == {"text": "unused"}
    assert rules[0]["help"] == {"text": "delete"}
    assert rules[0]["properties"] == {"tags": ["craftsmanship", "CG1"]}
    assert rules[1]["shortDescription"] == {"text": "Dup"}  # no smell: falls back to name
    results = run["results"]
    assert [r["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] for r in results] == [
        "a.py",
        "b.py",
    ]
    assert results[0]["ruleId"] == "dup" and results[0]["level"] == "warning"
    assert results[0]["message"] == {"text": "dup (CG3)"}
    assert results[0]["locations"][0]["physicalLocation"]["region"] == {"startLine": 7}
    assert results[1]["locations"][0]["physicalLocation"]["region"] == {"startLine": 1}  # clamped


def test_detector_list_shows_rules_tools_and_judgement_calls() -> None:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        craftcov.print_detector_list(CATALOG)

    lines = out.getvalue().splitlines()
    assert lines[0].startswith("CG1     dead")
    assert lines[0].endswith("ruff: F401, F841 + vulture")
    assert lines[1].endswith("— (needs judgment, see procedure)")
    assert lines[2].endswith("dupes")


# -- discovery and hashing ---------------------------------------------------------


def test_file_hash_is_the_sha256_of_the_content() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "f.py").write_bytes(b"abc")
        assert craftcov.file_hash(Path(tmp), "f.py") == (
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        )


def test_discovery_uses_git_when_it_can_and_globs_otherwise() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp).resolve()
        (root / "sub").mkdir()
        (root / "b.py").write_text("")
        (root / "sub" / "a.py").write_text("")
        (root / "ignored.py").write_text("")
        (root / "notes.txt").write_text("")
        assert craftcov.discover_python_files(root) == ["b.py", "ignored.py", "sub/a.py"]  # glob

        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(["git", "add", "b.py", "sub/a.py", "notes.txt"], cwd=root, check=True)
        assert craftcov.discover_python_files(root) == ["b.py", "sub/a.py"]  # tracked only


# -- corpus-wide findings ----------------------------------------------------------


def test_corpus_findings_are_appended_with_their_class_and_counterpart() -> None:
    body = "".join(f"        z{i} = {i}\n" for i in range(5))
    entry = {"id": "dup", "code": "CG3"}
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "a.py").write_text(f"class K:\n    def f(self):\n{body}")
        (root / "b.py").write_text(f"def g():\n    pass\n\nclass J:\n    def h(self):\n{body}")
        by_file: dict[str, list[dict]] = {"a.py": []}

        craftcov.merge_corpus_findings(
            root, ["a.py", "b.py"], by_file, {"dupes": {"entry": entry, "min_lines": 4}}
        )

    assert by_file["a.py"] == [
        {
            "line": 3,
            "col": 0,
            "tool": "dupes",
            "rule": None,
            "confidence": None,
            "heuristic_id": "dup",
            "heuristic_code": "CG3",
            "class": "K",
            "duplicate_of": "b.py:6-10",
            "dup_lines": 5,
        }
    ]
    assert by_file["b.py"][0]["class"] == "J"
    assert by_file["b.py"][0]["duplicate_of"] == "a.py:3-7"


def test_corpus_findings_default_to_eight_lines_and_need_the_dupes_tool() -> None:
    block = "".join(f"x{i} = {i}\n" for i in range(7))  # 7 lines: below the default of 8
    entry = {"id": "dup"}
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "a.py").write_text(block)
        (root / "b.py").write_text(block)
        by_file: dict[str, list[dict]] = {}

        craftcov.merge_corpus_findings(root, ["a.py", "b.py"], by_file, {"dupes": {"entry": entry}})
        assert by_file == {}
        craftcov.merge_corpus_findings(root, ["a.py", "b.py"], by_file, {})
        assert by_file == {}

        (root / "a.py").write_text(block + "x7 = 7\n")
        (root / "b.py").write_text(block + "x7 = 7\n")
        craftcov.merge_corpus_findings(root, ["a.py", "b.py"], by_file, {"dupes": {"entry": entry}})
        assert sorted(by_file) == ["a.py", "b.py"]
        assert by_file["a.py"][0]["heuristic_code"] == ""


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
    print(f"craftcov unit characterization passed ({len(tests)})")
