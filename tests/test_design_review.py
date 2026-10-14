"""design_review.py: advisory prompts for the design rules no gate can decide."""

from __future__ import annotations

import design_review as review

ALL = set(range(1, 200))
CONFIG_ERROR = 2
FEATURE, THREE_PARAMS = "feature", "3 parameters"
CAP, OVER_CAP, BEYOND = 5, 20, 15


def messages(source: str, added: set[int] = ALL) -> list[str]:
    return [n.message for n in review.review_source(source, added)]


def test_clean_small_function_gets_no_notes() -> None:
    assert messages("def add(a, b):\n    return a + b\n") == []


# -- flag arguments ------------------------------------------------------------------


def test_a_bool_annotated_parameter_is_a_flag_argument() -> None:
    notes = messages("def save(path, force: bool):\n    return path\n")

    assert any("flag argument `force`" in m for m in notes)


def test_a_boolean_default_is_a_flag_argument() -> None:
    notes = messages("def save(path, *, dry_run=False):\n    return path\n")

    assert any("flag argument `dry_run`" in m for m in notes)


def test_self_and_non_boolean_defaults_are_not_flags() -> None:
    assert messages("class C:\n    def go(self, n=3, label='x'):\n        return n\n") == []


# -- number of parameters --------------------------------------------------------------


def test_three_parameters_exceed_the_design_bar_but_not_the_gate() -> None:
    notes = messages("def f(a, b, c):\n    return a\n")

    assert any(THREE_PARAMS in m and "2 or fewer" in m for m in notes)


def test_two_parameters_are_fine_and_self_is_not_counted() -> None:
    assert messages("class C:\n    def f(self, a, b):\n        return a\n") == []


# -- one thing -------------------------------------------------------------------------


def test_a_name_with_and_in_it_is_questioned() -> None:
    notes = messages("def load_and_parse(x):\n    return x\n")

    assert any("says 'and'" in m for m in notes)


# -- command-query separation ------------------------------------------------------------


def test_a_getter_that_assigns_to_self_mixes_command_and_query() -> None:
    src = "class C:\n    def get_total(self):\n        self.cache = 1\n        return self.cache\n"

    assert any("command-query" in m for m in messages(src))


def test_a_query_that_mutates_its_argument_is_flagged() -> None:
    src = "def find_item(items):\n    items.append(1)\n    return items[0]\n"

    assert any("command-query" in m for m in messages(src))


def test_a_pure_getter_is_fine() -> None:
    assert messages("class C:\n    def get_total(self):\n        return self.total\n") == []


def test_a_command_that_mutates_is_fine() -> None:
    assert messages("def add_item(items):\n    items.append(1)\n") == []


# -- length ------------------------------------------------------------------------------


def test_a_long_function_is_questioned() -> None:
    body = "".join(f"    x{i} = {i}\n" for i in range(25))

    assert any("lines" in m for m in messages(f"def f():\n{body}    return x0\n"))


def test_a_function_at_the_limit_is_not() -> None:
    body = "".join(f"    x{i} = {i}\n" for i in range(18))

    assert not any("lines" in m for m in messages(f"def f():\n{body}    return x0\n"))


# -- only functions the change touched -----------------------------------------------------


def test_a_function_the_change_did_not_touch_is_not_reviewed() -> None:
    src = "def old(a, b, c):\n    return a\n\n\ndef new(x):\n    return x\n"

    assert messages(src, added={5, 6}) == []


def test_a_function_with_one_added_line_is_reviewed_whole() -> None:
    src = "def old(a, b, c):\n    return a\n"

    assert any(THREE_PARAMS in m for m in messages(src, added={2}))


def test_notes_carry_the_qualified_name_and_def_line() -> None:
    src = "class C:\n    def go(self, a, b, c):\n        return a\n"

    (note,) = review.review_source(src, ALL, path="m.py")

    assert (note.path, note.line, note.name) == ("m.py", 2, "C.go")


def test_a_syntax_error_yields_nothing_rather_than_crashing() -> None:
    assert review.review_source("def broken(:\n", ALL) == []


# -- rendering -------------------------------------------------------------------------------


def test_render_is_empty_without_notes() -> None:
    assert review.render_review([]) == ""


def test_render_says_it_is_advisory_and_lists_each_note() -> None:
    notes = [review.Note("a.py", 3, "f", THREE_PARAMS), review.Note("b.py", 9, "g", "x")]

    text = review.render_review(notes)

    assert "**Design review (advisory)**" in text
    assert "nothing here blocks" in text
    assert "| `a.py:3` | `f` | 3 parameters |" in text


def test_render_caps_the_list_and_counts_the_rest() -> None:
    notes = [review.Note("a.py", i, "f", "m") for i in range(1, OVER_CAP + 1)]

    text = review.render_review(notes, limit=CAP)

    assert text.count("| `a.py:") == CAP
    assert f"{BEYOND} more" in text


# -- against a real diff ---------------------------------------------------------------------


def test_review_diff_only_looks_at_functions_in_lines_the_branch_changed(repo) -> None:
    repo.commit("base", mod_py="def old(a, b, c):\n    return a\n")
    repo.branch(FEATURE)
    repo.commit(
        "more", mod_py="def old(a, b, c):\n    return a\n\n\ndef new(x, flag=True):\n    return x\n"
    )

    notes = review.review_diff(repo.path, "main")

    assert [n.name for n in notes] == ["new"]
    assert "flag argument `flag`" in notes[0].message


def test_review_diff_ignores_non_python_files(repo) -> None:
    repo.commit("base", notes_txt="a")
    repo.branch(FEATURE)
    repo.commit("more", notes_txt="def f(a, b, c): pass")

    assert review.review_diff(repo.path, "main") == []


def test_review_diff_skips_test_files_because_fixtures_are_not_a_design_signal(repo) -> None:
    repo.commit("base", mod_py="X = 1\n")
    repo.branch(FEATURE)
    repo.commit("more", test_mod_py="def test_x(a, b, c):\n    assert a\n")

    assert review.review_diff(repo.path, "main") == []


def test_the_cli_reports_an_unreadable_config_instead_of_crashing(repo, run_main, capsys) -> None:
    repo.write("craft-gate.toml", "[design-review]\nmax-lines = 0\n")
    repo.commit("base", mod_py="X = 1\n")
    repo.branch(FEATURE)
    repo.commit("more", mod_py="X = 2\n")

    code = run_main(review, "--base", "main", "--path", str(repo.path))

    assert code == CONFIG_ERROR
    assert "max-lines" in capsys.readouterr().err
