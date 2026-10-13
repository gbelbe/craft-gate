"""craftcov_pr_comment.py: the markdown report, sticky-comment logic, dry run."""

from __future__ import annotations

import json
import subprocess

import craftcov_pr_comment as pr_comment
import pytest
from craftcov import Summary

GUARD, DEAD = "guard-clauses", "dead-code"
CATALOG = {GUARD: {"id": GUARD, "code": "CG004"}}
SHA = "abc1234"
DRY_RUN = "--dry-run"
BASE = ("--base", "main")
PATH, FEATURE = "--path", "feature"
USAGE_ERROR, EXISTING_ID, LISTING_AND_PATCH = 2, 2, 2


def agg(total: int, **by_heuristic: int) -> Summary:
    return Summary(total, by_heuristic, {}, {}, {})


def render(base: Summary, head: Summary, repo_slug: str | None = "o/r") -> str:
    return pr_comment.render_markdown(base, head, CATALOG, repo_slug, SHA)


# -- render_markdown --------------------------------------------------------------


def test_the_body_starts_with_the_marker_that_makes_the_comment_sticky() -> None:
    assert render(agg(0), agg(0)).splitlines()[0] == pr_comment.MARKER


def test_total_going_down_is_shown_with_no_plus_sign() -> None:
    body = render(agg(5, a=5), agg(3, a=3))

    assert "**Repo-wide total: 5 → 3 (-2)**" in body


def test_total_going_up_is_shown_with_a_plus_sign() -> None:
    assert "**Repo-wide total: 1 → 4 (+3)**" in render(agg(1, a=1), agg(4, a=4))


def test_an_unchanged_total_has_no_sign_and_says_nothing_changed() -> None:
    body = render(agg(2, a=2), agg(2, a=2))

    assert "(0)**" in body
    assert "No change in any heuristic's count." in body
    assert "| Heuristic |" not in body


def test_changed_heuristics_get_a_table_row_each() -> None:
    body = render(
        agg(4, **{GUARD: 3, DEAD: 1}),
        agg(2, **{GUARD: 1, DEAD: 1}),
    )

    assert "| Code | Heuristic | Before | After | Δ |" in body
    assert f"| CG004 | `{GUARD}` | 3 | 1 | -2 |" in body
    assert DEAD not in body  # unchanged, so not listed


def test_a_newly_present_heuristic_is_flagged_new_and_a_resolved_one_done() -> None:
    body = render(agg(2, **{GUARD: 2}), agg(1, **{DEAD: 1}))

    assert f"| CG004 | `{GUARD}` | 2 | 0 | -2 ✅ |" in body
    assert f"|  | `{DEAD}` | 0 | 1 | +1 🆕 |" in body  # not in the catalog: blank code


def test_the_biggest_change_is_listed_first() -> None:
    body = render(agg(0), agg(6, **{"small": 1, "big": 5}))

    assert body.index("`big`") < body.index("`small`")


def test_the_footer_links_the_doc_at_the_exact_commit() -> None:
    body = render(agg(0), agg(0))

    assert f"[CRAFTSMANSHIP.md](https://github.com/o/r/blob/{SHA}/CRAFTSMANSHIP.md)" in body


def test_without_a_repo_slug_the_footer_is_plain_text() -> None:
    body = render(agg(0), agg(0), repo_slug=None)

    assert "see CRAFTSMANSHIP.md for what these mean" in body
    assert "https://github.com" not in body


# -- the sticky comment, with `gh` stubbed ----------------------------------------


class FakeGh:
    """Records every `gh` call; replies to the comment listing with `comments`."""

    def __init__(self, comments: list[dict] | str) -> None:
        self.comments = comments
        self.calls: list[list[str]] = []

    def __call__(self, cmd, **_):
        self.calls.append(cmd)
        out = self.comments if isinstance(self.comments, str) else json.dumps(self.comments)
        return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")


@pytest.fixture
def gh(monkeypatch):
    def install(comments):
        fake = FakeGh(comments)
        monkeypatch.setattr(pr_comment.subprocess, "run", fake)
        return fake

    return install


def test_the_existing_marker_comment_is_found_by_id(gh) -> None:
    gh([{"id": 1, "body": "unrelated"}, {"id": 2, "body": f"{pr_comment.MARKER}\nold"}])

    assert pr_comment.find_existing_comment("o/r", 7) == EXISTING_ID


def test_a_marker_that_is_not_at_the_start_does_not_count(gh) -> None:
    gh([{"id": 1, "body": f"quoting {pr_comment.MARKER}"}])

    assert pr_comment.find_existing_comment("o/r", 7) is None


def test_unparseable_gh_output_means_no_existing_comment(gh) -> None:
    gh("not json")

    assert pr_comment.find_existing_comment("o/r", 7) is None


def test_empty_gh_output_means_no_existing_comment(gh) -> None:
    gh("")

    assert pr_comment.find_existing_comment("o/r", 7) is None


def test_a_first_run_posts_a_new_comment(gh) -> None:
    fake = gh([])

    pr_comment.post_or_update_comment("o/r", 7, "BODY")

    assert fake.calls[-1] == [
        "gh", "api", "repos/o/r/issues/7/comments", "-X", "POST", "-f", "body=BODY"
    ]  # fmt: skip


def test_a_later_run_patches_the_existing_comment_in_place(gh) -> None:
    fake = gh([{"id": 99, "body": f"{pr_comment.MARKER} old"}])

    pr_comment.post_or_update_comment("o/r", 7, "BODY")

    assert fake.calls[-1] == [
        "gh", "api", "repos/o/r/issues/comments/99", "-X", "PATCH", "-f", "body=BODY"
    ]  # fmt: skip
    assert len(fake.calls) == LISTING_AND_PATCH  # one listing, one PATCH — never a second POST


# -- main -------------------------------------------------------------------------


def test_posting_requires_a_repo_and_a_pr(run_main, capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        run_main(pr_comment, *BASE)

    assert exc.value.code == USAGE_ERROR
    assert "--repo and --pr are required unless --dry-run" in capsys.readouterr().err


def test_a_dry_run_prints_the_real_before_and_after(repo, run_main, capsys) -> None:
    smelly = (
        "def f(x):\n    if x:\n        return 1\n    else:\n        return 2\n\n\nprint(f(1))\n"
    )
    repo.commit("base", mod_py=smelly)
    repo.branch(FEATURE)
    repo.commit("tidy: guard clause", mod_py=smelly.replace("else:\n        return 2", "return 2"))

    code = run_main(pr_comment, *BASE, PATH, str(repo.path), DRY_RUN)

    assert code == 0
    body = capsys.readouterr().out
    assert body.startswith(pr_comment.MARKER)
    assert "**Repo-wide total: 1 → 0 (-1)**" in body
    assert f"`{GUARD}` | 1 | 0 | -1 ✅" in body


def test_a_real_run_posts_and_reports_where(repo, run_main, gh, monkeypatch, capsys) -> None:
    repo.commit("base", mod_py="X = 1\n")
    repo.branch(FEATURE)
    repo.commit("more", mod_py="X = 2\n")
    real_run = subprocess.run
    fake = gh([])  # replaces subprocess.run; route git back to the real one
    monkeypatch.setattr(
        pr_comment.subprocess,
        "run",
        lambda cmd, **kw: real_run(cmd, **kw) if cmd[0] == "git" else fake(cmd, **kw),
    )

    code = run_main(pr_comment, *BASE, PATH, str(repo.path), "--repo", "o/r", "--pr", "7")

    assert code == 0
    assert "posted/updated on o/r#7" in capsys.readouterr().out
    assert any("POST" in call for call in fake.calls)


ONE, TWO = "X = 1\n", "X = 2\n"


def dry_run(repo, run_main, capsys, pyproject: str = "") -> str:
    """The comment body for a one-commit change to mod.py on a branch off main."""
    if pyproject:
        repo.write("pyproject.toml", pyproject)
    repo.commit("base", mod_py=ONE)
    repo.branch(FEATURE)
    repo.commit("more", mod_py=TWO)
    run_main(pr_comment, *BASE, PATH, str(repo.path), DRY_RUN)
    return capsys.readouterr().out


def test_a_dry_run_names_the_test_gates_the_repo_switched_off(repo, run_main, capsys) -> None:
    off = '[tool.craft-gate.mutation]\nenabled = false\nreason = "too slow"\n'

    body = dry_run(repo, run_main, capsys, pyproject=off)

    assert "**Gates switched off in this repo**" in body
    assert "| `mutation` | too slow |" in body
    assert body.index(pr_comment.MARKER) < body.index("Gates switched off")


def test_a_dry_run_has_no_switched_off_section_when_nothing_is_off(repo, run_main, capsys) -> None:
    assert "switched off" not in dry_run(repo, run_main, capsys)
