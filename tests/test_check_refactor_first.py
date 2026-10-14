"""check_refactor_first.py: touched-file discovery, the exemption, and the pass/fail verdict."""

from __future__ import annotations

import check_refactor_first as gate
import pytest

MOD, OTHER = "mod.py", "other.py"
CALL = "\n\nprint(f(1))\n"  # keeps f from being reported as dead code
CLEAN = "def f(x):\n    return x + 1\n" + CALL
# if/else after a return: one guard-clauses finding.
SMELLY = "def f(x):\n    if x:\n        return 1\n    else:\n        return 2\n" + CALL
# two smells: guard-clauses plus an unused function (dead-code).
SMELLIER = SMELLY + "\n\ndef unused_helper():\n    return 3\n"


@pytest.fixture
def project(repo, monkeypatch):
    """`main` holds one file; the test continues on branch `feature`."""
    repo.commit("base", mod_py=SMELLIER, other_py=CLEAN)
    repo.branch("feature")
    monkeypatch.chdir(repo.path)
    return repo


def verdict(run_main, repo, base: str = "main") -> int:
    return run_main(gate, "--base", base, "--path", str(repo.path))


# -- touched_python_files / has_tidy_exempt ---------------------------------------


def test_touched_files_lists_modified_and_added_python_files_only(project) -> None:
    base = project.sha("main")
    project.commit("change", mod_py=SMELLY, new_py=CLEAN, notes_txt="not python")

    pairs = gate.touched_python_files(project.path, base, "HEAD")

    assert sorted(pairs) == [(MOD, MOD), ("new.py", "new.py")]


def test_a_rename_reports_both_the_old_and_the_new_path(project) -> None:
    base = project.sha("main")
    project.git("mv", OTHER, "renamed.py")
    project.commit_staged("move")

    assert gate.touched_python_files(project.path, base, "HEAD") == [(OTHER, "renamed.py")]


def test_a_deleted_file_is_not_touched(project) -> None:
    base = project.sha("main")
    project.git("rm", "-q", OTHER)
    project.commit_staged("drop")

    assert gate.touched_python_files(project.path, base, "HEAD") == []


def test_tidy_exempt_is_found_only_at_the_start_of_a_trailer_line(project) -> None:
    base = project.sha("main")
    project.commit("mention\n\nwe discussed Tidy-Exempt: in review", mod_py=SMELLY)
    assert not gate.has_tidy_exempt(base, "HEAD", cwd=project.path)

    project.commit("real\n\nTidy-Exempt: spike", mod_py=CLEAN)
    assert gate.has_tidy_exempt(base, "HEAD", cwd=project.path)


def test_tidy_exempt_before_the_base_is_ignored(project) -> None:
    project.commit("old\n\nTidy-Exempt: long ago", mod_py=SMELLIER + "\n# x\n")
    base = project.sha()
    project.commit("new", mod_py=CLEAN)

    assert not gate.has_tidy_exempt(base, "HEAD", cwd=project.path)


# -- per_file_totals: real detectors ----------------------------------------------


def test_per_file_totals_counts_findings_and_omits_clean_files(project) -> None:
    totals = gate.per_file_totals(project.path)

    assert totals == {MOD: 2}


# -- main: the verdict ------------------------------------------------------------


def test_fixing_a_smell_in_a_touched_file_passes(project, run_main, capsys) -> None:
    project.commit(
        "tidy: guard clause", mod_py=SMELLIER.replace("else:\n        return 2", "return 2")
    )

    assert verdict(run_main, project) == 0
    assert "1 touched file(s) OK" in capsys.readouterr().out


def test_leaving_a_smelly_touched_file_unchanged_in_total_fails(project, run_main, capsys) -> None:
    project.commit("feat: touch", mod_py=SMELLIER + "\n# note\n")

    assert verdict(run_main, project) == 1
    assert f"{MOD}: 2 -> 2 (needed < 2)" in capsys.readouterr().err


def test_making_a_touched_file_smellier_fails(project, run_main, capsys) -> None:
    project.commit("feat: worse", mod_py=SMELLIER + "\n\ndef another_unused():\n    return 4\n")

    assert verdict(run_main, project) == 1
    assert f"{MOD}: 2 -> 3" in capsys.readouterr().err


def test_a_clean_file_must_stay_clean(project, run_main, capsys) -> None:
    project.commit("feat: dirty a clean file", other_py=SMELLY)

    assert verdict(run_main, project) == 1
    assert f"{OTHER}: 0 -> 1 (needed 0)" in capsys.readouterr().err


def test_a_clean_file_that_stays_clean_passes(project, run_main) -> None:
    project.commit("feat: more", other_py=CLEAN + "# a comment\n")

    assert verdict(run_main, project) == 0


def test_a_new_clean_file_passes_and_a_new_smelly_one_fails(project, run_main) -> None:
    project.commit("feat: new clean", fresh_py=CLEAN)
    assert verdict(run_main, project) == 0

    project.commit("feat: new smelly", fresher_py=SMELLY)
    assert verdict(run_main, project) == 1


def test_an_untouched_smelly_file_is_not_the_gates_business(project, run_main) -> None:
    project.commit("feat: elsewhere", other_py=CLEAN + "# a comment\n")

    assert verdict(run_main, project) == 0


def test_a_moved_file_is_compared_against_its_old_path(project, run_main) -> None:
    project.git("mv", MOD, "moved.py")
    project.write("moved.py", SMELLIER.replace("else:\n        return 2", "return 2"))
    project.git("add", "-A")
    project.commit_staged("move and tidy")

    assert verdict(run_main, project) == 0


def test_no_python_changes_means_nothing_to_check(project, run_main, capsys) -> None:
    project.commit("docs", readme_txt="hello")

    assert verdict(run_main, project) == 0
    assert capsys.readouterr().out == ""


def test_a_tidy_exempt_trailer_waives_the_per_file_ratchet(project, run_main, capsys) -> None:
    # mod.py stays at 2 findings, which the ratchet would refuse; the trailer waives that
    project.commit("fix: nudge\n\nTidy-Exempt: urgent", mod_py=SMELLIER + "# a comment\n")

    assert verdict(run_main, project) == 0
    assert "waiving: the per-file ratchet" in capsys.readouterr().out


def test_a_tidy_exempt_trailer_does_not_waive_a_smell_in_new_code(
    project, run_main, capsys
) -> None:
    project.commit("feat: worse\n\nTidy-Exempt: spike", other_py=SMELLY)

    assert verdict(run_main, project) == 1
    err = capsys.readouterr().err
    assert "new code is not clean" in err
    assert f"{OTHER}:4  CG001 guard-clauses" in err


def test_a_smell_on_an_added_line_fails_even_when_the_file_total_goes_down(
    project, run_main, capsys
) -> None:
    # fixes the guard clause and the dead helper, but adds a new unused function
    project.commit(
        "tidy: more\n",
        mod_py=SMELLY.replace("else:\n        return 2", "return 2")
        + "\n\ndef brand_new():\n    return 9\n",
    )

    assert verdict(run_main, project) == 1
    assert f"{MOD}:" in capsys.readouterr().err


def test_a_legacy_smell_on_a_line_the_change_did_not_touch_is_not_new_code(
    project, run_main
) -> None:
    project.commit("fix: only a comment\n\nTidy-Exempt: urgent", mod_py=SMELLIER + "# note\n")

    assert verdict(run_main, project) == 0


def test_a_base_ref_that_does_not_exist_is_skipped_with_a_warning(
    project, run_main, capsys
) -> None:
    project.commit("feat: worse", other_py=SMELLY)

    assert verdict(run_main, project, base="origin/nope") == 0
    assert "'origin/nope' not found locally" in capsys.readouterr().err
