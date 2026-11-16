"""check_knowledge.py: each rule catches the drift it exists for, and this repo's bundle holds."""

from __future__ import annotations

import posixpath

import check_knowledge as knowledge
import pytest
import yaml
from conftest import ROOT

SCRIPTS = "scripts"
ALPHA, BETA = "/g/alpha.md", "/g/beta.md"
HUB = "/g/index.md"
ALPHA_CODE, BETA_CODE = "scripts/alpha.py", "scripts/beta.py"
TYPE_GATE = "Gate"
FORMAT, LINKS, IMPORTS = "format", "links", "imports"


def concept(code: str | None, relations: dict[str, list[str]] | None = None, text: str = "") -> str:
    lines = ["---", f"type: {TYPE_GATE}"]
    if code:
        lines += ["code:", f"- {code}"]
    for kind, targets in (relations or {}).items():
        lines += ["relations:", f"  {kind}:", *(f"  - {t}" for t in targets)]
    return "\n".join([*lines, "---", text, ""])


def link(target: str, start: str = "/g") -> str:
    return f"[x]({posixpath.relpath(target, start)})"


@pytest.fixture
def project(tmp_path):
    """A repo with two scripts (alpha imports beta), an installer, and an empty bundle."""
    (tmp_path / SCRIPTS).mkdir()
    (tmp_path / ALPHA_CODE).write_text("import beta\n")
    (tmp_path / BETA_CODE).write_text("")
    (tmp_path / knowledge.INSTALLER).write_text(f"{ALPHA_CODE}\n")
    (tmp_path / knowledge.DOCS / "g").mkdir(parents=True)
    return tmp_path


def write(project, path: str, text: str) -> None:
    (project / knowledge.DOCS / path.lstrip("/")).write_text(text)


def faithful(project, alpha: str | None = None) -> None:
    write(project, ALPHA, alpha or concept(ALPHA_CODE))
    write(project, BETA, concept(BETA_CODE))
    write(project, HUB, f"{link(ALPHA)} {link(BETA)}\n")


def test_a_faithful_bundle_has_no_problem(project) -> None:
    faithful(project)

    assert knowledge.problems_in(project) == []


def test_parse_reads_the_frontmatter_and_the_links_of_the_text() -> None:
    text = concept(ALPHA_CODE, {IMPORTS: [BETA]}, text=f"See {link(BETA)}.")

    doc = knowledge.parse(text, ALPHA)

    assert doc.code == (ALPHA_CODE,)
    assert doc.relations == {IMPORTS: (BETA,)}
    assert doc.links == {BETA}
    assert doc.targets == {BETA}


def test_a_link_is_read_relative_to_its_file_and_an_external_one_is_not_a_link() -> None:
    text = "[a](../t/x.md) [b](y.md) [c](https://example.com/z.md)"

    assert knowledge.parse(text, "/g/a.md").links == {"/t/x.md", "/g/y.md"}


def test_parse_ignores_links_in_fenced_examples_and_reads_a_file_with_no_frontmatter() -> None:
    doc = knowledge.parse(f"```\n{link(BETA)}\n```\n", HUB)

    assert doc.meta == {}
    assert doc.links == frozenset()


def test_only_index_files_are_not_concepts() -> None:
    assert knowledge.parse("", HUB).is_concept is False
    assert knowledge.parse("", ALPHA).is_concept is True


def test_a_concept_without_a_type_is_reported(project) -> None:
    faithful(project)
    write(project, ALPHA, "---\ncode:\n- scripts/alpha.py\n---\n")

    assert knowledge.problems_in(project) == [f"{FORMAT}: {ALPHA} has no type"]


def test_an_unknown_relation_is_reported(project) -> None:
    faithful(project, concept(ALPHA_CODE, {"befriends": [BETA]}, text=link(BETA)))

    assert knowledge.problems_in(project) == [
        f"{FORMAT}: {ALPHA} uses the unknown relation 'befriends'"
    ]


def test_relations_that_are_not_a_mapping_are_reported(project) -> None:
    faithful(project)
    write(project, ALPHA, f"---\ntype: {TYPE_GATE}\ncode:\n- {ALPHA_CODE}\nrelations: [x]\n---\n")

    assert knowledge.problems_in(project) == [
        f"{FORMAT}: {ALPHA} relations must map a relation to a list"
    ]


def test_an_anchor_to_a_missing_path_is_reported(project) -> None:
    faithful(project)
    write(project, "/g/gone.md", concept("scripts/gone.py"))
    write(project, HUB, f"{link(ALPHA)} {link(BETA)} {link('/g/gone.md')}\n")

    assert knowledge.problems_in(project) == [
        "anchor: /g/gone.md points at scripts/gone.py, which does not exist"
    ]


def test_a_file_no_concept_owns_is_reported(project) -> None:
    faithful(project)
    (project / SCRIPTS / "new.py").write_text("")

    assert knowledge.problems_in(project) == ["coverage: scripts/new.py belongs to no concept"]


def test_a_directory_in_code_owns_the_files_below_it(project) -> None:
    faithful(project)
    (project / SCRIPTS / "pkg").mkdir()
    (project / SCRIPTS / "pkg" / "mod.py").write_text("")
    write(project, "/g/pkg.md", concept("scripts/pkg"))
    write(project, HUB, f"{link(ALPHA)} {link(BETA)} {link('/g/pkg.md')}\n")

    assert knowledge.problems_in(project) == []


def test_a_link_to_a_missing_file_is_reported(project) -> None:
    faithful(project)
    write(project, HUB, f"{link(ALPHA)} {link(BETA)} {link('/g/nowhere.md')}\n")

    assert knowledge.problems_in(project) == [
        f"{LINKS}: {HUB} links to /g/nowhere.md, which does not exist"
    ]


def test_a_concept_nothing_links_to_is_reported(project) -> None:
    faithful(project)
    write(project, HUB, f"{link(ALPHA)}\n")

    assert knowledge.problems_in(project) == [f"{LINKS}: {BETA} is linked from nowhere"]


def test_a_concept_that_only_links_to_itself_is_still_an_orphan(project) -> None:
    faithful(project)
    write(project, BETA, concept(BETA_CODE, text=link(BETA)))
    write(project, HUB, f"{link(ALPHA)}\n")

    assert knowledge.problems_in(project) == [f"{LINKS}: {BETA} is linked from nowhere"]


def test_a_relation_the_text_never_links_to_is_reported(project) -> None:
    faithful(project, concept(ALPHA_CODE, {IMPORTS: [BETA]}))

    assert knowledge.problems_in(project) == [
        f"prose: {ALPHA} declares imports {BETA} but its text never links to it"
    ]


def test_a_true_imports_relation_passes_and_a_false_one_is_reported(project) -> None:
    faithful(project, concept(ALPHA_CODE, {IMPORTS: [BETA]}, text=link(BETA)))
    assert knowledge.problems_in(project) == []

    faithful(project, concept(ALPHA_CODE))
    write(project, BETA, concept(BETA_CODE, {IMPORTS: [ALPHA]}, text=link(ALPHA)))
    assert knowledge.problems_in(project) == [f"{IMPORTS}: {BETA} does not import {ALPHA}"]


def test_an_installs_relation_must_name_something_the_installer_lists(project) -> None:
    boot = "/g/boot.md"
    faithful(project)
    write(project, boot, concept(None, {"installs": [ALPHA, BETA]}, text=link(ALPHA) + link(BETA)))
    write(project, HUB, f"{link(ALPHA)} {link(BETA)} {link(boot)}\n")

    assert knowledge.problems_in(project) == [
        f"installs: {knowledge.INSTALLER} does not list {BETA} (from {boot})"
    ]


def test_main_exits_one_and_prints_each_problem(project, capsys) -> None:
    faithful(project)
    (project / SCRIPTS / "new.py").write_text("")

    assert knowledge.main(["--path", str(project)]) == 1
    assert "✗ coverage: scripts/new.py belongs to no concept" in capsys.readouterr().err


def test_main_exits_zero_when_faithful(project, capsys) -> None:
    faithful(project)

    assert knowledge.main(["--path", str(project)]) == 0
    assert "✓" in capsys.readouterr().out


def test_this_repos_own_bundle_matches_the_repo() -> None:
    assert knowledge.problems_in(ROOT) == []


CHECK_COMMAND = "python3 tools/check_knowledge.py"


def test_ci_runs_the_checker_in_this_repo() -> None:
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text())
    runs = [s["run"] for job in workflow["jobs"].values() for s in job["steps"] if "run" in s]

    assert CHECK_COMMAND in runs


def test_the_agents_guidance_lists_the_checker_among_the_commands_to_run_before_a_commit() -> None:
    assert CHECK_COMMAND in (ROOT / "AGENTS.md").read_text()
