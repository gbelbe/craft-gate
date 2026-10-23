"""check_complexity_ratchet.py: the rule, the measurements, and the diff-aware CLI."""

from __future__ import annotations

import check_complexity_ratchet as ratchet
import pytest

THRESHOLD = ratchet.THRESHOLD
THREE_BRANCHES = 3
FLAT_COST, NESTED_COST = 2, 3  # two flat ifs; the inner of two nested ifs pays a nesting level
ERROR_EXIT = 2
MOVED = "pkg/new.py"
OLD_F = "old.py::f"


def branchy(name: str, branches: int) -> str:
    """A function whose cyclomatic complexity is branches + 1 (flat, so cognitive is the same)."""
    body = "".join(f"    if x == {i}:\n        r += {i}\n" for i in range(branches))
    return f"def {name}(x):\n    r = 0\n{body}    return r\n"


# -- find_violations: the ratchet rule on plain dicts -----------------------------


def test_a_new_function_over_the_threshold_is_refused() -> None:
    violations = ratchet.find_violations({}, {"a.py::f": THRESHOLD + 1})

    assert len(violations) == 1
    assert violations[0].startswith("a.py::f: new function with complexity 16 (> 15)")


def test_a_new_function_at_the_threshold_passes() -> None:
    assert ratchet.find_violations({}, {"a.py::f": THRESHOLD}) == []


def test_an_over_threshold_function_that_grew_is_refused() -> None:
    violations = ratchet.find_violations({"f": 20}, {"f": 21})

    assert len(violations) == 1
    assert "20 → 21" in violations[0]


def test_an_untouched_over_threshold_function_is_grandfathered() -> None:
    assert ratchet.find_violations({"f": 20}, {"f": 20}) == []
    assert ratchet.find_violations({"f": 20}, {"f": 20}, touched=set()) == []


def test_an_over_threshold_function_that_shrank_passes_even_if_still_over() -> None:
    assert ratchet.find_violations({"f": 20}, {"f": 18}, touched={"f"}) == []


def test_a_touched_over_threshold_function_must_strictly_decrease() -> None:
    violations = ratchet.find_violations({"f": 20}, {"f": 20}, touched={"f"})

    assert len(violations) == 1
    assert "unchanged at 20" in violations[0]


def test_a_touched_function_that_grew_reports_the_old_and_new_value() -> None:
    violations = ratchet.find_violations({"f": 20}, {"f": 22}, touched={"f"})

    assert "20 → 22" in violations[0]


def test_a_simple_function_pushed_over_the_threshold_is_refused() -> None:
    assert len(ratchet.find_violations({"f": THRESHOLD}, {"f": THRESHOLD + 1})) == 1


def test_the_metric_name_and_threshold_are_reported() -> None:
    violations = ratchet.find_violations({}, {"f": 5}, threshold=2, metric="widgets")

    assert violations == ["f: new function with widgets 5 (> 2) — keep new functions at or below 2"]


def test_violations_come_out_sorted_by_name() -> None:
    violations = ratchet.find_violations({}, {"b": 99, "a": 99})

    assert [v.split(":")[0] for v in violations] == ["a", "b"]


# -- the measurements -------------------------------------------------------------


def test_cyclomatic_complexity_counts_branches(tmp_path) -> None:
    (tmp_path / "m.py").write_text(branchy("f", THREE_BRANCHES))

    assert ratchet.compute_functions(tmp_path)["m.py::f"][0] == THREE_BRANCHES + 1


def test_methods_are_qualified_by_their_class(tmp_path) -> None:
    (tmp_path / "m.py").write_text("class C:\n    def go(self, x):\n        return x\n")

    assert "m.py::C.go" in ratchet.compute_functions(tmp_path)


def test_cognitive_complexity_charges_for_nesting(tmp_path) -> None:
    (tmp_path / "m.py").write_text(
        "def flat(x):\n    if x:\n        pass\n    if x:\n        pass\n"
        "def nested(x):\n    if x:\n        if x:\n            pass\n"
    )

    cog = ratchet.compute_cognitive(tmp_path)

    assert cog["m.py::flat"] == FLAT_COST
    assert cog["m.py::nested"] == NESTED_COST


def test_compute_complexity_reports_every_function_not_only_the_complex_ones(tmp_path) -> None:
    # The ratchet needs the small ones too: a simple function pushed over the line is a violation.
    (tmp_path / "m.py").write_text(branchy("big", THRESHOLD) + branchy("small", 2))

    assert ratchet.compute_complexity(tmp_path) == {"m.py::big": THRESHOLD + 1, "m.py::small": 3}


def test_an_invariant_return_is_detected(tmp_path) -> None:
    (tmp_path / "m.py").write_text(
        "def f(x):\n    out = []\n    if x:\n        return out\n"
        "    out.append(1)\n    return out\n"
    )

    assert ratchet.compute_invariant_returns(tmp_path) == {"m.py::f": "out"}


def test_a_rebound_name_is_not_an_invariant_return(tmp_path) -> None:
    (tmp_path / "m.py").write_text(
        "def f(x):\n    out = 1\n    if x:\n        return out\n    out = 2\n    return out\n"
    )

    assert ratchet.compute_invariant_returns(tmp_path) == {}


def test_repeated_literals_are_counted_per_file_and_keyed_by_repr(tmp_path) -> None:
    (tmp_path / "m.py").write_text(
        'a = "same-literal"\nb = "same-literal"\nc = "same-literal"\nd = "twice"\ne = "twice"\n'
        'f = "once-only"\ng = "x"\nh = "x"\n'
    )

    assert ratchet.compute_duplicate_literals(tmp_path) == {
        "m.py::'same-literal'": 3,
        "m.py::'twice'": 2,
    }  # "once-only" is a single use, "x" is below the minimum length


def test_a_docstring_does_not_count_as_a_duplicated_literal(tmp_path) -> None:
    (tmp_path / "m.py").write_text(
        '"""shared text"""\n\n\ndef f():\n    """shared text"""\n'
        '\n\ndef g():\n    """shared text"""\n'
    )

    assert ratchet.compute_duplicate_literals(tmp_path) == {}


# -- main(): end to end against a real repository ---------------------------------


@pytest.fixture
def project(repo, monkeypatch):
    """A repo whose base commit has one calm module; cwd is its root (the gate shells out there)."""
    repo.commit("base", mod_py=branchy("calm", 2))
    repo.branch("feature")
    monkeypatch.chdir(repo.path)
    return repo


def gate(run_main, *extra: str) -> int:
    return run_main(ratchet, "--base", "main", "--path", ".", *extra)


def test_a_change_that_stays_simple_passes(project, run_main, capsys) -> None:
    project.commit("feat: another", mod_py=branchy("calm", 2) + branchy("other", 3))

    assert gate(run_main) == 0
    assert "Complexity ratchet: OK" in capsys.readouterr().out


def test_a_new_complex_function_fails_with_its_name(project, run_main, capsys) -> None:
    project.commit("feat: big", mod_py=branchy("calm", 2) + branchy("big", THRESHOLD))

    assert gate(run_main) == 1
    err = capsys.readouterr().err
    assert "1 violation(s)" in err
    assert "mod.py::big: new function with cyclomatic complexity 16" in err


def test_a_touched_complex_function_must_come_out_lower(project, run_main, capsys) -> None:
    base = branchy("big", THRESHOLD + 2)
    project.commit("base big", mod_py=base)
    project.branch("main", reset=True)
    project.branch("touch")

    project.commit("touch: same", mod_py=base.replace("r = 0", "r = 0  # touched"))
    assert gate(run_main) == 1
    assert "unchanged at 18" in capsys.readouterr().err

    project.commit("tidy: simpler", mod_py=branchy("big", THRESHOLD + 1))
    assert gate(run_main) == 0


def test_a_function_the_diff_never_reaches_is_grandfathered(project, run_main) -> None:
    big = branchy("big", THRESHOLD + 2)
    project.commit("base big", mod_py=big)
    project.branch("main", reset=True)
    project.branch("elsewhere")

    project.commit("feat: unrelated", mod_py=big + branchy("small", 1))

    assert gate(run_main) == 0


def test_a_new_invariant_return_fails(project, run_main, capsys) -> None:
    project.commit(
        "feat: invariant",
        mod_py=branchy("calm", 2)
        + "def g(x):\n    out = []\n    if x:\n        return out\n    return out\n",
    )

    assert gate(run_main) == 1
    assert (
        "mod.py::g: every return hands back the same never-rebound 'out'" in capsys.readouterr().err
    )


def test_a_newly_triplicated_literal_fails(project, run_main, capsys) -> None:
    project.commit(
        "feat: literals",
        mod_py=branchy("calm", 2)
        + 'a = "repeated-text"\nb = "repeated-text"\nc = "repeated-text"\n',
    )

    assert gate(run_main) == 1
    assert "duplicated string literal" in capsys.readouterr().err


def exempt(code: str) -> dict[str, str]:
    return {"mod_py": code}


def test_a_tidy_exempt_trailer_still_refuses_a_new_complex_function(
    project, run_main, capsys
) -> None:
    project.commit(
        "feat: big\n\nTidy-Exempt: spike", **exempt(branchy("calm", 2) + branchy("big", THRESHOLD))
    )

    assert gate(run_main) == 1
    captured = capsys.readouterr()
    assert "waiving: debt rules" in captured.out
    assert "mod.py::big: new function with cyclomatic complexity 16" in captured.err


def test_a_tidy_exempt_trailer_waives_the_debt_rules_for_legacy_code(
    project, run_main, capsys
) -> None:
    base = branchy("big", THRESHOLD + 2)
    project.commit("base big", mod_py=base)
    project.branch("main", reset=True)
    project.branch("touch")

    project.commit("fix: nudge\n\nTidy-Exempt: urgent", **exempt(base.replace("r = 0", "r = 1")))

    assert gate(run_main) == 0
    assert "waiving: debt rules" in capsys.readouterr().out


def test_a_tidy_exempt_trailer_does_not_waive_a_new_invariant_return(project, run_main) -> None:
    project.commit(
        "feat: invariant\n\nTidy-Exempt: spike",
        **exempt(
            branchy("calm", 2)
            + "def g(x):\n    out = []\n    if x:\n        return out\n    return out\n"
        ),
    )

    assert gate(run_main) == 1


def test_a_tidy_exempt_trailer_does_not_waive_a_new_triplicated_literal(project, run_main) -> None:
    project.commit(
        "feat: literals\n\nTidy-Exempt: spike",
        **exempt(
            branchy("calm", 2) + 'a = "repeated-text"\nb = "repeated-text"\nc = "repeated-text"\n'
        ),
    )

    assert gate(run_main) == 1


def test_new_violations_ignore_names_the_base_already_had() -> None:
    violations = ratchet.find_new_violations({"old": 20}, {"old": 25, "new": 16})

    assert violations == [
        "new: new function with complexity 16 (> 15) — keep new functions at or below 15"
    ]


def test_an_unknown_base_ref_is_an_error(project, run_main, capsys) -> None:
    code = run_main(ratchet, "--base", "no-such-ref", "--path", ".")

    assert code == ERROR_EXIT
    assert "could not read base ref 'no-such-ref'" in capsys.readouterr().err


# -- follow_renames: a moved file keeps what it carried --------------------------------


def test_every_metric_of_a_moved_file_is_filed_under_its_new_path() -> None:
    base = ratchet.Measures(
        {OLD_F: 20, "same.py::g": 3},
        {OLD_F: 22},
        {OLD_F: "result"},
        {"old.py::'some text'": 4},
    )

    moved = ratchet.follow_renames(base, {"old.py": MOVED})

    assert moved.cc == {f"{MOVED}::f": 20, "same.py::g": 3}
    assert moved.cog == {f"{MOVED}::f": 22}
    assert moved.inv == {f"{MOVED}::f": "result"}
    assert moved.dup == {f"{MOVED}::'some text'": 4}


def test_without_renames_the_measures_are_unchanged() -> None:
    base = ratchet.Measures({"a.py::f": 1}, {}, {}, {})

    assert ratchet.follow_renames(base, {}) == base
